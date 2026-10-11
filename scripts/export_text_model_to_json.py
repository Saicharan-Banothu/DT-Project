import os
import json
import joblib
import numpy as np

def export_model():
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "text_model_v2.joblib"))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "text_model.json"))
    
    print(f"Loading {model_path}...")
    bundle = joblib.load(model_path)
    vec = bundle["vectorizer"]
    clf = bundle["model"]
    summary = bundle.get("summary", {})
    
    vocab = {str(k): int(v) for k, v in vec.vocabulary_.items()}
    vocab_size = len(vocab)
    print(f"Vocab size: {vocab_size}")
    
    idf = list(vec.idf_)
    coefs = list(clf.coef_[0])
    intercept = float(clf.intercept_[0])
    
    export_data = {
        "format_version": "1.0",
        "model_type": "tfidf_logistic_regression",
        "vocabulary_size": vocab_size,
        "ngram_range": [vec.ngram_range[0], vec.ngram_range[1]],
        "sublinear_tf": bool(getattr(vec, "sublinear_tf", True)),
        "norm": getattr(vec, "norm", "l2"),
        "intercept": round(intercept, 6),
        "vocabulary": vocab,
        "idf": [round(float(x), 6) for x in idf],
        "coefficients": [round(float(x), 6) for x in coefs],
        "calibration": summary.get("calibration", {})
    }
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f)
        
    print(f"Successfully exported {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    export_model()
