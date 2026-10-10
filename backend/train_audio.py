import os
import glob
import numpy as np
import librosa
import joblib
from sklearn.utils.class_weight import compute_class_weight
from xgboost import XGBClassifier
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

def extract_window_features(y, sr=16000, window_size=10):
    """
    Extract 98-dimensional acoustic feature vector per 10-second window
    matching the xgboost_scam_detector.py specification.
    """
    duration = librosa.get_duration(y=y, sr=sr)
    features = []

    if duration < window_size:
        step = max(1.0, duration)
        num_windows = 1
    else:
        step = window_size
        num_windows = int(duration // window_size)

    for i in range(num_windows):
        start_sec = i * step
        end_sec = min(duration, start_sec + window_size)
        start_sample = int(start_sec * sr)
        end_sample = int(end_sec * sr)
        segment = y[start_sample:end_sample]

        if len(segment) < sr:
            continue

        # MFCC + Delta + Delta-Delta (13 coefficients each)
        mfcc = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=13)
        delta_mfcc = librosa.feature.delta(mfcc)
        delta2_mfcc = librosa.feature.delta(mfcc, order=2)

        # Additional Features: Spectral Contrast, Chroma, Zero-Crossing Rate
        spectral_contrast = librosa.feature.spectral_contrast(y=segment, sr=sr)
        chroma = librosa.feature.chroma_stft(y=segment, sr=sr)
        zero_crossing = librosa.feature.zero_crossing_rate(y=segment)

        combined = np.hstack([
            np.mean(mfcc, axis=1), np.var(mfcc, axis=1),
            np.mean(delta_mfcc, axis=1), np.var(delta_mfcc, axis=1),
            np.mean(delta2_mfcc, axis=1), np.var(delta2_mfcc, axis=1),
            np.mean(spectral_contrast, axis=1),
            np.mean(chroma, axis=1),
            np.mean(zero_crossing)
        ])
        features.append(combined)

    if not features and len(y) > 500:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        delta_mfcc = librosa.feature.delta(mfcc)
        delta2_mfcc = librosa.feature.delta(mfcc, order=2)
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        zero_crossing = librosa.feature.zero_crossing_rate(y=y)
        combined = np.hstack([
            np.mean(mfcc, axis=1), np.var(mfcc, axis=1),
            np.mean(delta_mfcc, axis=1), np.var(delta_mfcc, axis=1),
            np.mean(delta2_mfcc, axis=1), np.var(delta2_mfcc, axis=1),
            np.mean(spectral_contrast, axis=1),
            np.mean(chroma, axis=1),
            np.mean(zero_crossing)
        ])
        features.append(combined)

    return features

def fast_time_stretch(y, rate=0.9):
    """Fast linear resample time stretch for audio augmentation without heavy phase vocoder delays."""
    indices = np.round(np.arange(0, len(y), rate)).astype(int)
    indices = indices[indices < len(y)]
    return y[indices]

def preprocess_all_audio_records(normal_dir="Normal calls", scam_dir="Scam calls"):
    """
    Load all audio files and extract features + augmentations once upfront.
    """
    valid_exts = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')
    normal_files = [f for f in glob.glob(os.path.join(normal_dir, "*.*")) if f.lower().endswith(valid_exts)]
    scam_files = [f for f in glob.glob(os.path.join(scam_dir, "*.*")) if f.lower().endswith(valid_exts)]

    print(f"Loading and processing {len(normal_files)} normal calls and {len(scam_files)} scam calls...")

    records = []

    for idx, path in enumerate(normal_files, 1):
        try:
            y, sr = librosa.load(path, sr=16000)
            base_feats = extract_window_features(y, sr=sr)
            records.append({
                'id': f"norm_{idx}",
                'path': path,
                'label': 0,
                'base_features': base_feats,
                'augmented_features': [] # No augmentation for normal class
            })
        except Exception as e:
            print(f"Skipping {path}: {e}")

    for idx, path in enumerate(scam_files, 1):
        try:
            y, sr = librosa.load(path, sr=16000)
            base_feats = extract_window_features(y, sr=sr)

            aug_feats = []
            # 1. Pitch shift (+2 semitones)
            try:
                ps_audio = librosa.effects.pitch_shift(y, sr=sr, n_steps=2)
                pf = extract_window_features(ps_audio, sr=sr)
                if pf: aug_feats.extend(pf)
            except Exception:
                pass

            # 2. Fast time stretch (0.9x speed)
            try:
                ts_audio = fast_time_stretch(y, rate=0.9)
                tf = extract_window_features(ts_audio, sr=sr)
                if tf: aug_feats.extend(tf)
            except Exception:
                pass

            # 3. Gaussian noise injection
            try:
                noise_audio = y + 0.005 * np.random.randn(len(y))
                nf = extract_window_features(noise_audio, sr=sr)
                if nf: aug_feats.extend(nf)
            except Exception:
                pass

            records.append({
                'id': f"scam_{idx}",
                'path': path,
                'label': 1,
                'base_features': base_feats,
                'augmented_features': aug_feats
            })
        except Exception as e:
            print(f"Skipping {path}: {e}")

    print(f"Successfully processed {len(records)} audio files into memory.")
    return records

def train_and_evaluate_audio_model(model_save_path="models/audio_xgb_model.joblib"):
    records = preprocess_all_audio_records()
    if not records:
        raise ValueError("No audio records loaded from Normal calls or Scam calls.")

    labels = np.array([r['label'] for r in records])
    records_arr = np.array(records, dtype=object)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accuracies, precisions, recalls, f1s, rocs = [], [], [], [], []
    all_y_true, all_y_pred = [], []

    print("\n" + "="*60)
    print(" 5-FOLD STRATIFIED CROSS-VALIDATION (AUDIO XGBOOST PIPELINE)")
    print("="*60)

    for fold, (train_idx, val_idx) in enumerate(skf.split(records_arr, labels), 1):
        train_recs = records_arr[train_idx]
        val_recs = records_arr[val_idx]

        # Training set gets base features + augmented features
        X_train, y_train = [], []
        for r in train_recs:
            if r['base_features']:
                X_train.extend(r['base_features'])
                y_train.extend([r['label']] * len(r['base_features']))
            if r['label'] == 1 and r['augmented_features']:
                X_train.extend(r['augmented_features'])
                y_train.extend([1] * len(r['augmented_features']))

        # Validation set gets only pure unaugmented base features
        X_val, y_val = [], []
        for r in val_recs:
            if r['base_features']:
                X_val.extend(r['base_features'])
                y_val.extend([r['label']] * len(r['base_features']))

        X_train, y_train = np.array(X_train), np.array(y_train)
        X_val, y_val = np.array(X_val), np.array(y_val)

        if len(X_val) == 0 or len(np.unique(y_val)) < 2:
            continue

        # Class weights
        classes = np.unique(y_train)
        weights = compute_class_weight("balanced", classes=classes, y=y_train)
        scale_pos = weights[1] / weights[0] if len(weights) > 1 else 1.0

        model = XGBClassifier(
            n_estimators=160,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=scale_pos,
            random_state=42,
            eval_metric="logloss"
        )
        model.fit(X_train, y_train)

        y_pred = model.predict(X_val)
        y_prob = model.predict_proba(X_val)[:, 1]

        acc = accuracy_score(y_val, y_pred)
        prec = precision_score(y_val, y_pred, zero_division=0)
        rec = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)
        try:
            roc = roc_auc_score(y_val, y_prob)
        except Exception:
            roc = 0.5

        accuracies.append(acc)
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        rocs.append(roc)
        all_y_true.extend(y_val)
        all_y_pred.extend(y_pred)

        print(f"Fold {fold}: Acc={acc*100:.2f}% | Prec={prec*100:.2f}% | Rec={rec*100:.2f}% | F1={f1*100:.2f}% | ROC-AUC={roc:.4f}")

    print("\n" + "-"*60)
    print(" HONEST MEAN CROSS-VALIDATED METRICS (AUDIO XGBOOST)")
    print("-"*60)
    print(f" Mean Accuracy:  {np.mean(accuracies)*100:.2f}% (±{np.std(accuracies)*100:.2f}%)")
    print(f" Mean Precision: {np.mean(precisions)*100:.2f}% (±{np.std(precisions)*100:.2f}%)")
    print(f" Mean Recall:    {np.mean(recalls)*100:.2f}% (±{np.std(recalls)*100:.2f}%)")
    print(f" Mean F1-Score:  {np.mean(f1s)*100:.2f}% (±{np.std(f1s)*100:.2f}%)")
    print(f" Mean ROC-AUC:   {np.mean(rocs):.4f} (±{np.std(rocs):.4f})")

    cm = confusion_matrix(all_y_true, all_y_pred)
    print("\nAggregate Confusion Matrix (Rows: Actual [Normal, Scam], Cols: Predicted [Normal, Scam]):")
    print(cm)

    # Train final full model on all samples with full augmentation
    print("\nTraining final full XGBoost audio model on all dataset windows...")
    X_full, y_full = [], []
    for r in records:
        if r['base_features']:
            X_full.extend(r['base_features'])
            y_full.extend([r['label']] * len(r['base_features']))
        if r['label'] == 1 and r['augmented_features']:
            X_full.extend(r['augmented_features'])
            y_full.extend([1] * len(r['augmented_features']))

    X_full, y_full = np.array(X_full), np.array(y_full)
    weights = compute_class_weight("balanced", classes=np.unique(y_full), y=y_full)
    scale_pos = weights[1] / weights[0] if len(weights) > 1 else 1.0

    final_model = XGBClassifier(
        n_estimators=180,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        scale_pos_weight=scale_pos,
        random_state=42,
        eval_metric="logloss"
    )
    final_model.fit(X_full, y_full)

    os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
    bundle = {
        'model': final_model,
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
    print(f"Saved trained audio XGBoost model bundle to {model_save_path}")
    return bundle

if __name__ == "__main__":
    train_and_evaluate_audio_model()
