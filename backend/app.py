from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.classifier import PromptClassifier, DATASET
from backend.schemas import ClassifyRequest, ClassifyResponse

EVENTS_DB = ROOT / "data" / "events.sqlite3"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
if FRONTEND_URL:
    ALLOWED_ORIGINS.append(FRONTEND_URL)

classifier = PromptClassifier()


def connect_events_db():
    EVENTS_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(EVENTS_DB, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database():
    with connect_events_db() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS events "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
            "prompt_preview TEXT NOT NULL, category TEXT NOT NULL, confidence REAL NOT NULL, "
            "risk_score INTEGER NOT NULL, risk_level TEXT NOT NULL, action TEXT NOT NULL, "
            "explanation TEXT NOT NULL, probabilities TEXT NOT NULL)"
        )


@asynccontextmanager
async def lifespan(application: FastAPI):
    initialize_database()
    classifier.train()
    yield


app = FastAPI(
    title="GuardPost AI API",
    version="2.0.0",
    description="Dataset-based prompt injection classification. No LLM is used.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "model": "TF-IDF + Logistic Regression",
        "dataset": DATASET.name,
        "llm_enabled": False,
    }


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
    except (RuntimeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=500, detail="Classification failed.") from exc

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with connect_events_db() as connection:
            connection.execute(
                "INSERT INTO events "
                "(timestamp, prompt_preview, category, confidence, risk_score, risk_level, "
                "action, explanation, probabilities) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp,
                    prompt[:180],
                    result["category"],
                    result["confidence"],
                    result["risk_score"],
                    result["risk_level"],
                    result["action"],
                    result["explanation"],
                    json.dumps(result["probabilities"]),
                ),
            )
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="Could not store classification event.") from exc

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
    if not DATASET.exists():
        raise HTTPException(status_code=503, detail="Dataset file is unavailable.")

    try:
        df = pd.read_csv(DATASET)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, OSError) as exc:
        raise HTTPException(status_code=500, detail="Could not read the dataset.") from exc

    if "label" not in df.columns:
        raise HTTPException(status_code=500, detail="Dataset is missing the label column.")

    return {
        "filename": DATASET.name,
        "rows": int(len(df)),
        "labels": {str(key): int(value) for key, value in df["label"].value_counts().items()},
        "columns": list(df.columns),
    }
