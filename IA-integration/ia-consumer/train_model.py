"""Train and record metrics at the exact runtime threshold."""
import hashlib
import json
import math
import os
from importlib.metadata import version
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from ot_common import threshold

DATASET_PATH = Path("dataset_sensori.xlsx")
MODEL_PATH = Path("model_random_forest.joblib")
METRICS_PATH = Path("training_metrics.json")


def validate_dataset(df):
    required = {"value", "tipo", "unit", "is_anomaly"}
    if required - set(df.columns):
        raise ValueError("Missing dataset columns")
    df = df.copy()
    if df[list(required)].isna().any().any():
        raise ValueError("Missing dataset values")
    if df["value"].map(lambda v: isinstance(v, bool)).any():
        raise ValueError("Boolean sensor values are invalid")
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    if not np.isfinite(df["value"]).all():
        raise ValueError("Non-finite values")
    if set(df["is_anomaly"].unique()) != {0, 1}:
        raise ValueError("Dataset labels must be exactly 0 and 1")
    if df["is_anomaly"].value_counts().min() < 5:
        raise ValueError("At least five rows per class are required for the 80/20 split")
    if not ((df["tipo"].eq("temp") & df["unit"].eq("C")) | (df["tipo"].eq("hum") & df["unit"].eq("%"))).all():
        raise ValueError("Unsupported tipo/unit combination")
    df["is_anomaly"] = df["is_anomaly"].astype(int)
    return df


def load_dataset(path):
    return validate_dataset(pd.read_excel(path))


def build_pipeline():
    return Pipeline([
        ("preprocessor", ColumnTransformer([
            ("num", "passthrough", ["value"]),
            ("cat", OneHotEncoder(handle_unknown="error"), ["tipo", "unit"]),
        ])),
        ("classifier", RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced")),
    ])


def runtime_metrics(y, scores, cutoff):
    prediction = (np.asarray(scores) >= cutoff).astype(int)
    return {"classification_report": classification_report(y, prediction, labels=[0, 1], output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist()}


def check_quality(metrics):
    # No fabricated acceptance target: configured gates are explicit and recorded.
    gates = {}
    for metric, variable in (("recall", "MIN_ANOMALY_RECALL"), ("precision", "MIN_ANOMALY_PRECISION")):
        value = os.getenv(variable)
        if value is not None and value != "":
            limit = float(value)
            if not math.isfinite(limit) or not 0 <= limit <= 1:
                raise ValueError(f"Invalid {variable}")
            gates[metric] = limit
    metrics["quality_gates"] = gates
    metrics["quality_status"] = "passed" if gates else "not_configured"
    for metric, limit in gates.items():
        if metrics["runtime"]["classification_report"]["1"][metric] < limit:
            metrics["quality_status"] = "failed"
    return metrics["quality_status"] != "failed"


def main():
    # A failed run must not leave a previous model eligible for release.
    MODEL_PATH.unlink(missing_ok=True)
    df = load_dataset(DATASET_PATH)
    X_train, X_test, y_train, y_test = train_test_split(
        df[["value", "tipo", "unit"]], df["is_anomaly"], test_size=0.2, random_state=42, stratify=df["is_anomaly"])
    if set(y_train) != {0, 1} or set(y_test) != {0, 1}:
        raise ValueError("Both splits must contain both classes")
    model = build_pipeline().fit(X_train, y_train)
    cutoff = threshold()
    scores = model.predict_proba(X_test)[:, list(model.classes_).index(1)]
    metrics = {
        "dataset_rows": len(df), "train_rows": len(X_train), "test_rows": len(X_test),
        "class_counts": {str(k): int(v) for k, v in df.is_anomaly.value_counts().items()},
        "threshold": cutoff, "runtime": runtime_metrics(y_test, scores, cutoff),
        "classifier": classification_report(y_test, model.predict(X_test), output_dict=True, zero_division=0),
        "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        "dependencies": {p: version(p) for p in ("scikit-learn", "pandas", "numpy", "scipy", "joblib")},
        "features": ["value", "tipo", "unit"], "split": "stratified random 80/20, seed 42",
    }
    accepted = check_quality(metrics)
    if accepted:
        joblib.dump(model, MODEL_PATH)
        metrics["model_sha256"] = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    if not accepted:
        raise RuntimeError("Configured quality gates failed")


if __name__ == "__main__":
    main()
