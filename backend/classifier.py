
from pathlib import Path
import math
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "prompt_dataset.csv"

RISK_POLICY = {
    "safe": 5,
    "prompt_injection": 75,
    "jailbreak": 90,
    "data_exfiltration": 95,
    "unsafe_request": 85,
}

DESCRIPTIONS = {
    "safe": "The model found this prompt most similar to benign examples in the training dataset.",
    "prompt_injection": "The prompt resembles attempts to override, manipulate, or disclose instruction context.",
    "jailbreak": "The prompt resembles attempts to bypass safety restrictions or policy boundaries.",
    "data_exfiltration": "The prompt resembles attempts to obtain credentials, secrets, or private information.",
    "unsafe_request": "The prompt resembles a harmful or disallowed request represented in the training dataset.",
}

class PromptClassifier:
    def __init__(self):
        self.pipeline = None
        self.labels = []
        self.evaluation = None

    @staticmethod
    def _new_pipeline():
        return Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=12000,
                                      strip_accents="unicode", sublinear_tf=True)),
            ("classifier", LogisticRegression(max_iter=1200, class_weight="balanced",
                                               random_state=42))
        ])

    def train(self):
        if not DATASET.exists():
            raise FileNotFoundError(f"Dataset not found: {DATASET}")
        df = pd.read_csv(DATASET).dropna(subset=["text", "label"])
        df["text"] = df["text"].astype(str).str.strip()
        df["label"] = df["label"].astype(str).str.strip()
        df = df[(df.text != "") & (df.label != "")]
        if df.label.nunique() < 2:
            raise ValueError("Dataset must contain at least two distinct labels.")
        self.labels = sorted(df.label.unique().tolist())
        label_counts = df.label.value_counts()
        if label_counts.min() >= 2:
            test_size = max(len(self.labels), math.ceil(len(df) * 0.2))
            if test_size < len(df):
                train_text, test_text, train_labels, test_labels = train_test_split(
                    df.text, df.label, test_size=test_size, random_state=42,
                    stratify=df.label
                )
                evaluation_pipeline = self._new_pipeline()
                evaluation_pipeline.fit(train_text, train_labels)
                predictions = evaluation_pipeline.predict(test_text)
                report = classification_report(
                    test_labels, predictions, labels=self.labels,
                    output_dict=True, zero_division=0
                )
                self.evaluation = {
                    "available": True,
                    "test_size": int(len(test_text)),
                    "accuracy": round(float(accuracy_score(test_labels, predictions)), 4),
                    "labels": self.labels,
                    "per_class": {
                        label: {
                            "precision": round(float(report[label]["precision"]), 4),
                            "recall": round(float(report[label]["recall"]), 4),
                            "f1": round(float(report[label]["f1-score"]), 4),
                            "support": int(report[label]["support"]),
                        }
                        for label in self.labels
                    },
                    "confusion_matrix": confusion_matrix(
                        test_labels, predictions, labels=self.labels
                    ).tolist(),
                }
            else:
                self.evaluation = {"available": False}
        else:
            self.evaluation = {"available": False}

        self.pipeline = self._new_pipeline()
        self.pipeline.fit(df.text, df.label)
        return {"rows": int(len(df)), "labels": self.labels,
                "evaluation": self.evaluation}

    def predict(self, prompt: str):
        if self.pipeline is None:
            self.train()
        probabilities = self.pipeline.predict_proba([prompt])[0]
        classes = self.pipeline.classes_
        idx = int(probabilities.argmax())
        category = str(classes[idx])
        confidence = float(probabilities[idx])
        score = RISK_POLICY.get(category, 60)
        if category == "safe":
            level, action = "Low", "ALLOW"
        elif score >= 90:
            level, action = "Critical", "BLOCK"
        elif score >= 80:
            level, action = "High", "BLOCK"
        else:
            level, action = "Elevated", "BLOCK"
        return {
            "category": category,
            "confidence": round(confidence, 4),
            "risk_score": score,
            "risk_level": level,
            "action": action,
            "explanation": DESCRIPTIONS.get(category, "Predicted category from the training dataset."),
            "probabilities": {str(c): round(float(p), 4) for c, p in zip(classes, probabilities)}
        }
