import json
import joblib
import pandas as pd
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATASET_PATH = Path("dataset_sensori.xlsx")
MODEL_PATH = Path("model_random_forest.joblib")
METRICS_PATH = Path("training_metrics.json")


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)

    required = {"value", "tipo", "unit", "is_anomaly"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti nel dataset: {sorted(missing)}")

    df = df.dropna(subset=["value", "tipo", "unit", "is_anomaly"]).copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["is_anomaly"] = df["is_anomaly"].astype(int)

    return df


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", ["value"]),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["tipo", "unit"]),
        ]
    )

    classifier = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])


def main():
    df = load_dataset(DATASET_PATH)

    X = df[["value", "tipo", "unit"]]
    y = df["is_anomaly"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = build_pipeline()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()

    metrics = {
        "dataset_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "anomaly_rate": float(df["is_anomaly"].mean()),
        "classification_report": report,
        "confusion_matrix": cm,
        "features": ["value", "tipo", "unit"],
        "target": "is_anomaly",
    }

    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("Training completato")
    print(json.dumps(metrics, indent=2))
    print(f"Modello salvato in: {MODEL_PATH}")


if __name__ == "__main__":
    main()