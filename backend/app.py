
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.classifier import PromptClassifier, DATASET
from backend.schemas import ClassifyRequest, ClassifyResponse

EVENTS_DB = ROOT / "data" / "events.sqlite3"

app = FastAPI(title="GuardPost AI API", version="2.0.0",
              description="Dataset-based prompt injection classification. No LLM is used.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = PromptClassifier()


def connect_events_db():
    return sqlite3.connect(EVENTS_DB)

@app.on_event("startup")
def startup():
    with connect_events_db() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS events "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
            "prompt_preview TEXT NOT NULL, category TEXT NOT NULL, confidence REAL NOT NULL, "
            "risk_score INTEGER NOT NULL, risk_level TEXT NOT NULL, action TEXT NOT NULL, "
            "explanation TEXT NOT NULL, probabilities TEXT NOT NULL)"
        )
    classifier.train()

@app.get("/api/health")
def health():
    return {"status": "online", "model": "TF-IDF + Logistic Regression",
            "dataset": str(DATASET.name), "llm_enabled": False}

@app.get("/api/overview")
def overview():
    with connect_events_db() as connection:
        total, blocked, allowed = connection.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN action = 'ALLOW' THEN 1 ELSE 0 END) "
            "FROM events"
        ).fetchone()
        category_rows = connection.execute(
            "SELECT category, COUNT(*) FROM events GROUP BY category"
        ).fetchall()
    return {
        "total_scanned": total,
        "blocked": blocked or 0,
        "allowed": allowed or 0,
        "categories": dict(category_rows),
        "labels": classifier.labels,
    }

@app.get("/api/evaluation")
def evaluation():
    return classifier.evaluation

@app.post("/api/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest):
    prompt = request.prompt.strip()
    if len(prompt) < 3:
        raise HTTPException(status_code=422, detail="Enter at least 3 characters.")
    try:
        result = classifier.predict(prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect_events_db() as connection:
        cursor = connection.execute(
            "INSERT INTO events "
            "(timestamp, prompt_preview, category, confidence, risk_score, risk_level, "
            "action, explanation, probabilities) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, prompt[:180], result["category"], result["confidence"],
             result["risk_score"], result["risk_level"], result["action"],
             result["explanation"], json.dumps(result["probabilities"]))
        )
    return result

@app.get("/api/events")
def get_events():
    with connect_events_db() as connection:
        rows = connection.execute(
            "SELECT id, timestamp, prompt_preview, category, confidence, risk_score, "
            "risk_level, action FROM events ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [
        {
            "id": row[0],
            "timestamp": row[1],
            "prompt_preview": row[2],
            "category": row[3],
            "confidence": row[4],
            "risk_score": row[5],
            "risk_level": row[6],
            "action": row[7],
        }
        for row in rows
    ]

@app.get("/api/dataset-info")
def dataset_info():
    import pandas as pd
    df = pd.read_csv(DATASET)
    return {
        "filename": DATASET.name,
        "rows": int(len(df)),
        "labels": {str(k): int(v) for k, v in df["label"].value_counts().items()},
        "columns": list(df.columns)
    }
