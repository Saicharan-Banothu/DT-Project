import os
import re
import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
)

def clean_text(text: str) -> str:
    """Preprocess text by lowercasing, normalizing spaces and retaining essential punctuation/numbers."""
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    # Normalize excessive spaces and tabs
    text = re.sub(r'\s+', ' ', text)
    return text

def load_text_dataset(filepath: str):
    """Load fraud_call.txt safely handling tabs, quotes, and inconsistent columns."""
    labels, texts = [], []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                raw_label, text = parts
                raw_label = raw_label.strip().lower()
                # 1 = fraud/scam, 0 = normal
                label = 1 if 'fraud' in raw_label or 'scam' in raw_label else 0
                labels.append(label)
                texts.append(clean_text(text))
            elif len(parts) == 1:
                # Fallback if comma or space separated
                parts_comma = line.split(',', 1)
                if len(parts_comma) == 2 and parts_comma[0].strip().lower() in ['fraud', 'normal', 'scam', 'ham']:
                    label = 1 if parts_comma[0].strip().lower() in ['fraud', 'scam'] else 0
                    labels.append(label)
                    texts.append(clean_text(parts_comma[1]))
                    
    df = pd.DataFrame({'text': texts, 'label': labels})
    print(f"Loaded {len(df)} total rows from {filepath}")
    print(f"Class breakdown: Normal (0): {(df['label'] == 0).sum()}, Fraud (1): {(df['label'] == 1).sum()}")
    return df

def train_and_evaluate_text_model(data_path="fraud_call.txt", model_save_path="models/text_model.joblib"):
    df = load_text_dataset(data_path)
    X = df['text'].values
    y = df['label'].values

    # 5-Fold Stratified Cross Validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    accuracies, precisions, recalls, f1s, rocs = [], [], [], [], []
    all_y_true, all_y_pred = [], []

    print("\n" + "="*60)
    print(" 5-FOLD STRATIFIED CROSS-VALIDATION (TEXT PIPELINE)")
    print("="*60)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y), 1):
        X_train_fold, X_val_fold = X[train_idx], X[val_idx]
        y_train_fold, y_val_fold = y[train_idx], y[val_idx]

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=6000,
            sublinear_tf=True,
            min_df=2
        )
        X_train_vec = vectorizer.fit_transform(X_train_fold)
        X_val_vec = vectorizer.transform(X_val_fold)

        clf = LogisticRegression(
            class_weight='balanced',
            C=3.0,
            max_iter=1000,
            random_state=42
        )
        clf.fit(X_train_vec, y_train_fold)

        y_pred = clf.predict(X_val_vec)
        y_prob = clf.predict_proba(X_val_vec)[:, 1]

        acc = accuracy_score(y_val_fold, y_pred)
        prec = precision_score(y_val_fold, y_pred, zero_division=0)
        rec = recall_score(y_val_fold, y_pred, zero_division=0)
        f1 = f1_score(y_val_fold, y_pred, zero_division=0)
        roc = roc_auc_score(y_val_fold, y_prob)

        accuracies.append(acc)
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        rocs.append(roc)
        all_y_true.extend(y_val_fold)
        all_y_pred.extend(y_pred)

        print(f"Fold {fold}: Acc={acc*100:.2f}% | Prec={prec*100:.2f}% | Rec={rec*100:.2f}% | F1={f1*100:.2f}% | ROC-AUC={roc:.4f}")

    print("\n" + "-"*60)
    print(" HONEST MEAN CROSS-VALIDATED METRICS (TEXT PIPELINE)")
    print("-"*60)
    print(f" Mean Accuracy:  {np.mean(accuracies)*100:.2f}% (±{np.std(accuracies)*100:.2f}%)")
    print(f" Mean Precision: {np.mean(precisions)*100:.2f}% (±{np.std(precisions)*100:.2f}%)")
    print(f" Mean Recall:    {np.mean(recalls)*100:.2f}% (±{np.std(recalls)*100:.2f}%)")
    print(f" Mean F1-Score:  {np.mean(f1s)*100:.2f}% (±{np.std(f1s)*100:.2f}%)")
    print(f" Mean ROC-AUC:   {np.mean(rocs):.4f} (±{np.std(rocs):.4f})")
    
    cm = confusion_matrix(all_y_true, all_y_pred)
    print("\nAggregate Confusion Matrix (Rows: Actual [Normal, Fraud], Cols: Predicted [Normal, Fraud]):")
    print(cm)
    print("\nDetailed Classification Report:")
    print(classification_report(all_y_true, all_y_pred, target_names=['Normal', 'Fraud']))

    # Train final model on full dataset
    print("Training final full text pipeline on all rows...")
    final_vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=6000,
        sublinear_tf=True,
        min_df=2
    )
    X_vec = final_vectorizer.fit_transform(X)
    final_clf = LogisticRegression(
        class_weight='balanced',
        C=3.0,
        max_iter=1000,
        random_state=42
    )
    final_clf.fit(X_vec, y)

    os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
    bundle = {
        'vectorizer': final_vectorizer,
        'model': final_clf,
        'cv_metrics': {
            'accuracy': float(np.mean(accuracies)),
            'precision': float(np.mean(precisions)),
            'recall': float(np.mean(recalls)),
            'f1': float(np.mean(f1s)),
            'roc_auc': float(np.mean(rocs)),
            'confusion_matrix': cm.tolist()
        }
    }
    joblib.dump(bundle, model_save_path)
    print(f"Saved trained text model bundle to {model_save_path}")
    return bundle

if __name__ == "__main__":
    train_and_evaluate_text_model()
