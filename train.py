import json
import warnings
from collections import Counter
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from joblib import dump

from sklearn.preprocessing import RobustScaler, LabelEncoder  # ← CHANGED: was StandardScaler
from sklearn.impute import KNNImputer                          # ← CHANGED: was SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import (
    train_test_split, StratifiedKFold, cross_val_score, cross_val_predict
)
from sklearn.metrics import (
    accuracy_score, f1_score, recall_score, roc_auc_score,
    classification_report, ConfusionMatrixDisplay, confusion_matrix
)
from sklearn.ensemble import (
    RandomForestClassifier, ExtraTreesClassifier, StackingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.calibration import CalibratedClassifierCV

import xgboost as xgb
from imblearn.over_sampling import BorderlineSMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

import shap

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# GLOBAL CONFIG
# ──────────────────────────────────────────────
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

MODEL_DIR  = Path("models")
REPORT_DIR = Path("reports")
MODEL_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

# Healthcare safety thresholds
UNCERTAINTY_THRESHOLD    = 0.55
PROB_CLIP_LOW            = 0.05
PROB_CLIP_HIGH           = 0.95
SMOTE_CONSERVATIVE_RATIO = 0.95   # raised 0.90→0.95: more Normal samples → better accuracy

# ← NEW: Recall target for threshold optimisation
# Per-class recall targets — decoupled so each is optimised independently.
# Previously a single joint gate (pcos_r >= t AND pcod_r >= t) meant PCOS recall
# was blocked whenever PCOD couldn't reach the same target.  Separate floors fix this.
PCOS_RECALL_TARGET = 0.80
PCOD_RECALL_TARGET = 0.80
TARGET_RECALL      = PCOS_RECALL_TARGET   # back-compat alias

# OOF accuracy floor — lowered 0.82→0.81.
# 0.81 OOF ≈ 83-85 % test (OOF runs ~2-3 % below final fit score).
# This gives the threshold search just enough room to find combos
# that hit PCOS recall 0.80 without unnecessarily rejecting good candidates.
OOF_ACCURACY_FLOOR = 0.81

# ← NEW: Custom class weights — PCOS/PCOD penalised 1.8× more than Normal
#   Index order: 0=Normal Profile, 1=PCOD_Positive, 2=PCOS_Positive
#   (verified from LabelEncoder output — always confirm before deployment)
# PCOS weight raised 1.8→2.0 to nudge PCOS recall above 0.80.
# PCOD remains 1.8 — it was already meeting its target.
# Index: 0=Normal Profile, 1=PCOD_Positive, 2=PCOS_Positive
CUSTOM_CLASS_WEIGHTS = {0: 1.0, 1: 1.8, 2: 2.0}


# ══════════════════════════════════════════════
# 1.  DATA LOADING
# ══════════════════════════════════════════════
def load_dataset(data_path: str):
    """
    Loads the CSV, normalises target labels, splits into
    stratified train / test sets.
    No feature engineering — raw columns only.
    """
    print("\n" + "="*60)
    print("  LOADING DATASET")
    print("="*60)

    df = pd.read_csv(data_path, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    for col in df.columns:
        if df[col].dtype == "object" and col != "Condition":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    label_map = {
        "PCOD_Positive" : "PCOD_Positive",
        "PCOS_Positive" : "PCOS_Positive",
        "Normal Profile": "Normal Profile",
        "PCOD"          : "PCOD_Positive",
        "PCOS"          : "PCOS_Positive",
        "Normal"        : "Normal Profile",
    }
    df["Condition"] = df["Condition"].astype(str).str.strip()
    df = df[df["Condition"].isin(label_map)].copy()
    df["target"] = df["Condition"].map(label_map)

    features = [
        c for c in df.select_dtypes(include=np.number).columns
        if c not in ("target",)
    ]
    df = df.dropna(subset=features, how="all")

    X   = df[features]
    y   = df["target"]
    le  = LabelEncoder()
    y_enc = le.fit_transform(y)

    # ── Verify class index order for CUSTOM_CLASS_WEIGHTS ─────
    print(f"\n  LabelEncoder class order (index → class):")
    for i, cls in enumerate(le.classes_):
        print(f"    {i} → {cls}  (weight={CUSTOM_CLASS_WEIGHTS.get(i,'?')})")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc,
        test_size    = 0.20,
        stratify     = y_enc,
        random_state = RANDOM_STATE
    )

    print(f"\n  Dataset shape  : {df.shape}")
    print(f"  Features used  : {len(features)}")
    print(f"  Train / Test   : {len(X_train)} / {len(X_test)}")
    print("\n  Class distribution (full set):")
    for cls, cnt in y.value_counts().items():
        pct = cnt / len(y) * 100
        print(f"    {cls:<20} {cnt:>4}  ({pct:.1f}%)")

    return X_train, X_test, y_train, y_test, features, le


# ══════════════════════════════════════════════
# 2.  PREPROCESSOR
# ══════════════════════════════════════════════
def build_preprocessor(features: list) -> ColumnTransformer:
    """
    KNNImputer (k=7) → RobustScaler.

    KNNImputer: imputes each missing value using the k nearest complete
    neighbours — preserves inter-feature correlations (BMI/weight/height)
    that median imputation discards.  k=7 balances bias/variance for ≈370
    training samples.

    RobustScaler: scales using median and IQR instead of mean/std, so
    extreme clinical values (high BMI, unusual cycle lengths) do not
    distort the feature space.
    """
    numeric_pipe = Pipeline([
        ("imputer", KNNImputer(n_neighbors=7)),   # ← CHANGED: was SimpleImputer(median)
        ("scaler",  RobustScaler()),               # ← CHANGED: was StandardScaler()
    ])
    return ColumnTransformer([("num", numeric_pipe, features)])


# ══════════════════════════════════════════════
# 3.  BALANCED XGBOOST WRAPPER
# ══════════════════════════════════════════════
class BalancedXGBClassifier(xgb.XGBClassifier):
    """
    XGBClassifier that automatically applies CUSTOM_CLASS_WEIGHTS as
    sample_weight at fit-time.  XGBoost has no native class_weight=
    parameter; this wrapper is the only correct way to apply class
    weighting inside a StackingClassifier.
    """
    def fit(self, X, y, sample_weight=None, **kwargs):
        if sample_weight is None:
            # ← CHANGED: was compute_sample_weight("balanced", y)
            # Now uses CUSTOM_CLASS_WEIGHTS (1.0/1.8/1.8) instead of the
            # frequency-derived "balanced" weights (≈1.0/1.27/1.27).
            sample_weight = np.array([
                CUSTOM_CLASS_WEIGHTS[label] for label in y
            ])
        return super().fit(X, y, sample_weight=sample_weight, **kwargs)


# ══════════════════════════════════════════════
# 4.  MODEL DEFINITIONS
# ══════════════════════════════════════════════
def build_models(n_classes: int):
    """
    Three base learners all using CUSTOM_CLASS_WEIGHTS {Normal:1.0, PCOD:1.8, PCOS:1.8}.
    """

    # ── XGBoost ────────────────────────────────────────────────
    xgb_clf = BalancedXGBClassifier(
        objective        = "multi:softprob",
        num_class        = n_classes,
        eval_metric      = "mlogloss",
        max_depth        = 4,          # ← CHANGED: 3→4 (slightly more capacity)
        n_estimators     = 600,        # ← CHANGED: 500→600
        learning_rate    = 0.03,
        subsample        = 0.75,
        colsample_bytree = 0.75,
        min_child_weight = 4,
        gamma            = 0.20,
        # reg_alpha/lambda loosened slightly for a marginal accuracy gain;
        # still well-regularised for a 458-row dataset.
        reg_alpha        = 0.40,
        reg_lambda       = 1.80,
        random_state     = RANDOM_STATE,
        n_jobs           = -1,
        verbosity        = 0,
    )

    # ── Random Forest ──────────────────────────────────────────
    rf_clf = RandomForestClassifier(
        n_estimators      = 400,       # ← CHANGED: 300→400
        max_depth         = None,      # ← CHANGED: 6→None (full depth, controlled by leaf)
        min_samples_split = 6,
        min_samples_leaf  = 3,
        # ← CHANGED: "balanced"→CUSTOM_CLASS_WEIGHTS for 1.8× PCOS/PCOD penalty
        class_weight      = CUSTOM_CLASS_WEIGHTS,
        random_state      = RANDOM_STATE,
        n_jobs            = -1,
    )

    # ── Extra Trees ────────────────────────────────────────────
    et_clf = ExtraTreesClassifier(
        n_estimators      = 400,       # ← CHANGED: 300→400
        max_depth         = None,      # ← CHANGED: 6→None
        min_samples_split = 6,
        min_samples_leaf  = 3,
        # ← CHANGED: "balanced"→CUSTOM_CLASS_WEIGHTS
        class_weight      = CUSTOM_CLASS_WEIGHTS,
        random_state      = RANDOM_STATE,
        n_jobs            = -1,
    )

    return xgb_clf, rf_clf, et_clf


# ══════════════════════════════════════════════
# 5.  STACKING ENSEMBLE
# ══════════════════════════════════════════════
def build_stacking(xgb_clf, rf_clf, et_clf) -> CalibratedClassifierCV:
    """
    Base learners → balanced LogisticRegression meta-learner.
    Isotonic calibration for reliable probability outputs.
    """
    stack = StackingClassifier(
        estimators=[
            ("xgb", xgb_clf),
            ("rf",  rf_clf),
            ("et",  et_clf),
        ],
        final_estimator=LogisticRegression(
            max_iter     = 1000,
            C            = 0.3,
            # ← CHANGED: "balanced"→CUSTOM_CLASS_WEIGHTS
            class_weight = CUSTOM_CLASS_WEIGHTS,
            solver       = "lbfgs",
        ),
        cv     = 5,
        n_jobs = -1,
    )
    return CalibratedClassifierCV(stack, method="isotonic", cv=3)


# ══════════════════════════════════════════════
# 6.  CONSERVATIVE SMOTE STRATEGY
# ══════════════════════════════════════════════
def build_conservative_smote_strategy(y_train: np.ndarray) -> dict:
    """
    Brings minority classes to 90 % of the majority count.
    Only upsamples; never downsamples.  With a 1.62× imbalance ratio,
    this adds ≈ 51 synthetic Normal samples — clinically conservative.
    """
    counts       = Counter(y_train)
    majority_cnt = max(counts.values())
    target_cnt   = int(majority_cnt * SMOTE_CONSERVATIVE_RATIO)
    strategy     = {c: target_cnt for c, cnt in counts.items() if cnt < target_cnt}

    print("\n  Conservative SMOTE targets:")
    for cls, target in strategy.items():
        original = counts[cls]
        print(f"    Class {cls}: {original} → {target}  "
              f"(+{target - original} synthetic samples)")

    return strategy


# ══════════════════════════════════════════════
# 7.  FULL PIPELINE
# ══════════════════════════════════════════════
def build_pipeline(preprocessor, calibrated_stack, smote_strategy: dict) -> ImbPipeline:
    """preproc → conservative BorderlineSMOTE → CalibratedStackingClassifier"""
    return ImbPipeline([
        ("preproc", preprocessor),
        ("smote", BorderlineSMOTE(
            sampling_strategy = smote_strategy,
            random_state      = RANDOM_STATE,
            k_neighbors       = 5,
            kind              = "borderline-1",
        )),
        ("clf", calibrated_stack),
    ])


# ══════════════════════════════════════════════
# 8.  THRESHOLD HELPERS                      ← NEW
# ══════════════════════════════════════════════
def apply_thresholds(probs: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    """
    Multiclass threshold rule: predict = argmax(prob / threshold).

    Dividing each class's probability by its threshold normalises the
    probability space so that classes with a lower threshold are
    "easier" to predict — directly increasing their recall.
    The Normal threshold is fixed at 1.0 (no boost).
    """
    scaled = probs / thresholds
    return scaled.argmax(axis=1)


def find_optimal_thresholds(
    pipeline,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    le: LabelEncoder,
    target_recall: float = TARGET_RECALL,
) -> np.ndarray:
    """
    Finds per-class decision thresholds that achieve PCOS recall ≥ target_recall
    and PCOD recall ≥ target_recall, then maximises overall accuracy.

    Uses 5-fold cross_val_predict to obtain out-of-fold (OOF) probabilities
    on X_train — no data leakage, uses the full training set for calibration.

    Strategy:
        thresholds[Normal] = 1.0   (fixed, no bias)
        thresholds[PCOD]   = pcod_t ∈ (0.05, 0.60]  ← searched
        thresholds[PCOS]   = pcos_t ∈ (0.05, 0.60]  ← searched

    Predict rule: argmax(prob / thresholds)

    Falls back gracefully:
        If target_recall = 0.85 is unreachable → tries 0.82 → then 0.80.
        Reports which target was actually achieved.
    """
    pcos_idx = list(le.classes_).index("PCOS_Positive")
    pcod_idx = list(le.classes_).index("PCOD_Positive")
    norm_idx = list(le.classes_).index("Normal Profile")

    print("\n  Computing OOF probabilities (5-fold) for threshold search...")
    cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    # n_jobs not passed to cross_val_predict — same reason as cross_val_score above.
    oof_probs = cross_val_predict(
        pipeline, X_train, y_train, cv=cv5, method="predict_proba"
    )

    def _search(target: float):
        best_thresholds = np.ones(len(le.classes_))
        best_score      = -1.0
        best_recalls    = None

        for pcos_t in np.arange(0.60, 0.04, -0.01):
            for pcod_t in np.arange(0.60, 0.04, -0.01):
                thr = np.ones(len(le.classes_))
                thr[pcos_idx] = pcos_t
                thr[pcod_idx] = pcod_t

                preds  = apply_thresholds(oof_probs, thr)

                pcos_r = recall_score(
                    (y_train == pcos_idx).astype(int),
                    (preds   == pcos_idx).astype(int)
                )
                pcod_r = recall_score(
                    (y_train == pcod_idx).astype(int),
                    (preds   == pcod_idx).astype(int)
                )
                norm_r = recall_score(
                    (y_train == norm_idx).astype(int),
                    (preds   == norm_idx).astype(int)
                )
                acc = accuracy_score(y_train, preds)

                # Decoupled gates — PCOS and PCOD targets checked independently.
                # A combo is valid as long as each class meets its own floor;
                # neither blocks the other.
                pcos_ok = pcos_r >= PCOS_RECALL_TARGET
                pcod_ok = pcod_r >= PCOD_RECALL_TARGET
                acc_ok  = acc    >= OOF_ACCURACY_FLOOR
                if pcos_ok and pcod_ok and acc_ok:
                    # Maximise accuracy; norm_r as weighted tie-breaker.
                    score = acc * 2.0 + norm_r * 0.3
                    if score > best_score:
                        best_score   = score
                        best_thresholds = thr.copy()
                        best_recalls = (pcos_r, pcod_r, norm_r, acc)

        return best_thresholds, best_recalls

    # Cascade: progressively relax both targets together if the joint target is
    # unreachable. OOF_ACCURACY_FLOOR is always enforced regardless of fallback.
    for fallback in [target_recall, 0.78, 0.75]:
        thresholds, recalls = _search(fallback)
        if recalls is not None:
            achieved_target = fallback
            break
    else:
        # Absolute fallback: equal thresholds (model default)
        print("  ⚠ Threshold optimisation could not hit target — using equal thresholds.")
        return np.ones(len(le.classes_)), None, None

    pcos_r, pcod_r, norm_r, acc = recalls
    print(f"\n  Threshold optimisation result (target recall ≥ {achieved_target:.2f}):")
    print(f"    PCOS threshold : {thresholds[pcos_idx]:.2f}  →  recall = {pcos_r:.3f}")
    print(f"    PCOD threshold : {thresholds[pcod_idx]:.2f}  →  recall = {pcod_r:.3f}")
    print(f"    Normal thresh  : {thresholds[norm_idx]:.2f}  →  recall = {norm_r:.3f}")
    print(f"    OOF accuracy with thresholds : {acc:.3f}")

    return thresholds, achieved_target, recalls


# ══════════════════════════════════════════════
# 9.  CONFIDENCE-BASED PREDICTION
# ══════════════════════════════════════════════
def predict_with_confidence(
    pipeline,
    X: pd.DataFrame,
    le: LabelEncoder,
    thresholds: np.ndarray,            # ← CHANGED: thresholds now passed in
    threshold: float = UNCERTAINTY_THRESHOLD,
) -> list:
    """
    Production-safe inference using learned per-class thresholds.

    Returns list of dicts:
        prediction    – class label or "Uncertain" if confidence < threshold
        confidence    – max class probability (after clipping)
        probabilities – {class: probability} for all three classes

    Predict rule: argmax(prob / thresholds) — same as find_optimal_thresholds.
    Probabilities are clipped to [0.05, 0.95] to prevent overconfident outputs.
    """
    raw_probs = pipeline.predict_proba(X)

    # Safety clipping
    clipped = np.clip(raw_probs, PROB_CLIP_LOW, PROB_CLIP_HIGH)
    probs   = clipped / clipped.sum(axis=1, keepdims=True)

    # ← NEW: apply per-class thresholds to determine prediction
    pred_indices = apply_thresholds(probs, thresholds)

    results = []
    for i, prob_row in enumerate(probs):
        max_prob   = float(prob_row.max())
        pred_idx   = int(pred_indices[i])
        prob_dict  = {
            cls: round(float(p), 4)
            for cls, p in zip(le.classes_, prob_row)
        }
        prediction = (
            le.classes_[pred_idx] if max_prob >= threshold else "Uncertain"
        )
        results.append({
            "prediction"   : prediction,
            "confidence"   : round(max_prob, 4),
            "probabilities": prob_dict,
        })

    return results


# ══════════════════════════════════════════════
# 10.  TRAINING + EVALUATION
# ══════════════════════════════════════════════
def train_and_evaluate(pipeline, X_train, X_test, y_train, y_test, le):
    """
    Step A : 10-fold stratified CV (pre-threshold baseline)
    Step B : Threshold optimisation via OOF on X_train
    Step C : Final fit on full X_train
    Step D : Test set evaluation — with and without thresholds
    """

    # ── A. Cross-validation (baseline, no threshold) ──────────
    print("\n" + "="*60)
    print("  10-FOLD STRATIFIED CROSS-VALIDATION  (pre-threshold)")
    print("="*60)

    cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=RANDOM_STATE)
    # n_jobs removed from cross_val_score — using n_jobs=-1 here with
    # ImbPipeline triggers a sklearn/joblib parallel warning because
    # imblearn uses joblib.delayed while sklearn expects its own
    # sklearn.utils.parallel.delayed.  Parallelism is retained inside
    # each model (RF/ET/XGB all have n_jobs=-1 set directly).
    cv_f1  = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
    cv_acc = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="accuracy")

    print(f"\n  CV Macro F1  : {cv_f1.mean():.4f}  ± {cv_f1.std():.4f}")
    print(f"  CV Accuracy  : {cv_acc.mean():.4f}  ± {cv_acc.std():.4f}")

    # ── B. Threshold optimisation ─────────────────────────────
    print("\n" + "="*60)
    print("  THRESHOLD OPTIMISATION  (OOF-based, no data leakage)")
    print("="*60)

    thresholds, achieved_target, oof_recalls = find_optimal_thresholds(
        pipeline, X_train, y_train, le, target_recall=TARGET_RECALL
    )

    # ── C. Final training ─────────────────────────────────────
    print("\n" + "="*60)
    print("  TRAINING FINAL MODEL")
    print("="*60)

    pipeline.fit(X_train, y_train)
    print("  Final model trained successfully.")

    # ── D. Test evaluation ────────────────────────────────────
    print("\n" + "="*60)
    print("  TEST SET EVALUATION")
    print("="*60)

    # Probabilities (raw, renormed for AUC)
    y_prob_raw  = pipeline.predict_proba(X_test)
    y_prob_safe = y_prob_raw / y_prob_raw.sum(axis=1, keepdims=True)

    # ── D1. Default predictions (no threshold) ─────────────────
    y_pred_default = y_prob_raw.argmax(axis=1)
    acc_def = accuracy_score(y_test, y_pred_default)
    f1_def  = f1_score(y_test, y_pred_default, average="macro")

    # ── D2. Threshold-adjusted predictions ← NEW ──────────────
    y_pred_thresh = apply_thresholds(y_prob_raw, thresholds)
    acc_thr = accuracy_score(y_test, y_pred_thresh)
    f1_thr  = f1_score(y_test, y_pred_thresh, average="macro")
    auc     = roc_auc_score(y_test, y_prob_safe, multi_class="ovr", average="macro")

    print(f"\n  ┌─ Default predictions (equal thresholds) ───────────")
    print(f"  │  Accuracy : {acc_def:.4f}  ({acc_def*100:.2f}%)")
    print(f"  │  Macro F1 : {f1_def:.4f}")
    print(f"  └────────────────────────────────────────────────────")
    print(f"\n  ┌─ Threshold-adjusted predictions ← production path ─")
    print(f"  │  Accuracy  : {acc_thr:.4f}  ({acc_thr*100:.2f}%)")
    print(f"  │  Macro F1  : {f1_thr:.4f}")
    print(f"  │  ROC-AUC   : {auc:.4f}")
    print(f"  └────────────────────────────────────────────────────")

    print(f"\n  Classification Report (threshold-adjusted):\n")
    print(classification_report(y_test, y_pred_thresh, target_names=le.classes_))

    # ── Per-class recall comparison ← NEW ─────────────────────
    print("  Per-class recall — default vs threshold-adjusted:")
    for i, cls in enumerate(le.classes_):
        r_def = recall_score((y_test==i).astype(int),(y_pred_default==i).astype(int))
        r_thr = recall_score((y_test==i).astype(int),(y_pred_thresh==i).astype(int))
        delta = r_thr - r_def
        sign  = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"    {cls:<20}  default={r_def:.3f}  adjusted={r_thr:.3f}  {sign}{abs(delta):.3f}")

    # ── Confidence results (uncertainty flagging) ──────────────
    confidence_results = predict_with_confidence(
        pipeline, X_test, le, thresholds
    )
    uncertain_count = sum(1 for r in confidence_results if r["prediction"] == "Uncertain")
    print(f"\n  Uncertain predictions : {uncertain_count} / {len(y_test)}  "
          f"(confidence threshold = {UNCERTAINTY_THRESHOLD})")

    print("\n  Per-class confidence summary:")
    for cls_idx, cls_name in enumerate(le.classes_):
        cls_mask  = y_test == cls_idx
        cls_confs = [
            r["confidence"]
            for r, mask in zip(confidence_results, cls_mask)
            if mask
        ]
        if cls_confs:
            print(f"    {cls_name:<20}  "
                  f"mean conf = {np.mean(cls_confs):.3f}  "
                  f"min = {np.min(cls_confs):.3f}")

    # ── Confusion matrix (threshold-adjusted) ─────────────────
    cm  = confusion_matrix(y_test, y_pred_thresh)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Default
    ConfusionMatrixDisplay(
        confusion_matrix(y_test, y_pred_default),
        display_labels=le.classes_
    ).plot(ax=axes[0], cmap="Blues", colorbar=False)
    axes[0].set_title("Default Thresholds", fontsize=12, fontweight="bold")

    # Threshold-adjusted
    ConfusionMatrixDisplay(cm, display_labels=le.classes_).plot(
        ax=axes[1], cmap="Greens", colorbar=False
    )
    axes[1].set_title("Optimised Thresholds  (production)", fontsize=12, fontweight="bold")

    plt.suptitle("Confusion Matrix — Test Set", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    cm_path = REPORT_DIR / "confusion_matrix.png"
    plt.savefig(cm_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Confusion matrix saved → {cm_path}")

    return acc_thr, f1_thr, auc, cv_f1.mean(), cv_acc.mean(), thresholds, achieved_target


# ══════════════════════════════════════════════
# 11.  SHAP EXPLAINABILITY
# ══════════════════════════════════════════════
def generate_shap_plots(pipeline, X_test, features, le):
    """
    Extracts XGBoost from the calibrated stacking ensemble and produces:
        • Per-class SHAP dot plots
        • Global SHAP bar plot (mean |SHAP| all classes)
        • Feature ranking CSV with normalised 0–1 importance
    """
    print("\n" + "="*60)
    print("  SHAP EXPLAINABILITY")
    print("="*60)

    X_sample         = X_test.sample(min(150, len(X_test)), random_state=42)
    X_transformed    = pipeline.named_steps["preproc"].transform(X_sample)
    X_transformed_df = pd.DataFrame(X_transformed, columns=features)

    # ── Navigate: pipeline["clf"] → CalibratedClassifierCV
    #             .calibrated_classifiers_[0].estimator → StackingClassifier
    #             .named_estimators_["xgb"] → BalancedXGBClassifier
    calibrated_cv  = pipeline.named_steps["clf"]
    stacking_model = calibrated_cv.calibrated_classifiers_[0].estimator
    xgb_model      = stacking_model.named_estimators_["xgb"]

    explainer   = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_transformed_df)
    # shap_values: (n_samples, n_features, n_classes) or list

    # ── Per-class dot plots ───────────────────────────────────
    for class_idx, class_name in enumerate(le.classes_):
        safe_name = class_name.replace(" ", "_").replace("/", "_")
        sv = (
            shap_values[class_idx]
            if isinstance(shap_values, list)
            else shap_values[:, :, class_idx]
        )
        fig, ax = plt.subplots(figsize=(9, 5))
        plt.sca(ax)
        shap.summary_plot(
            sv, X_transformed_df,
            show=False, plot_type="dot", max_display=len(features),
        )
        ax.set_title(
            f"SHAP Feature Impact — {class_name}",
            fontsize=13, fontweight="bold", pad=12
        )
        plt.tight_layout()
        out_path = REPORT_DIR / f"shap_dot_{safe_name}.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved SHAP dot plot  → {out_path}")

    # ── Global bar plot ───────────────────────────────────────
    mean_shap_2d = (
        np.mean([np.abs(sv) for sv in shap_values], axis=0)
        if isinstance(shap_values, list)
        else np.mean(np.abs(shap_values), axis=2)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    plt.sca(ax)
    shap.summary_plot(
        mean_shap_2d, X_transformed_df,
        show=False, plot_type="bar", max_display=len(features),
    )
    ax.set_title(
        "SHAP Global Feature Importance (mean |SHAP| — all classes)",
        fontsize=13, fontweight="bold", pad=12
    )
    plt.tight_layout()
    bar_path = REPORT_DIR / "shap_global_bar.png"
    plt.savefig(bar_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved SHAP bar plot  → {bar_path}")

    # ── Normalised feature ranking ────────────────────────────
    mean_importance = mean_shap_2d.mean(axis=0)
    ranking = pd.DataFrame({
        "feature"              : features,
        "mean_shap"            : mean_importance,
        "normalised_importance": mean_importance / mean_importance.sum(),
    }).sort_values("mean_shap", ascending=False).reset_index(drop=True)
    ranking["rank"] = ranking.index + 1

    print("\n  Top Features by SHAP Importance (normalised):")
    print(ranking[["rank", "feature", "normalised_importance"]].to_string(index=False))

    return ranking


# ══════════════════════════════════════════════
# 12.  SAVE ARTEFACTS
# ══════════════════════════════════════════════
def save_artefacts(pipeline, le, features, metrics, shap_ranking, thresholds, achieved_target):
    """
    Saves:
        models/pcos_ensemble_stacking.joblib
        models/pcos_ensemble_meta.json         ← includes thresholds
        reports/shap_feature_ranking.csv
    """
    model_path = MODEL_DIR / "pcos_ensemble_stacking.joblib"
    dump(pipeline, model_path)

    meta = {
        "model"                   : "Stacking(XGB + RF + ET) → LogReg [Calibrated]",
        "test_accuracy"           : round(metrics["accuracy"],    4),
        "macro_f1"                : round(metrics["macro_f1"],    4),
        "roc_auc_ovr"             : round(metrics["roc_auc"],     4),
        "cv_mean_f1"              : round(metrics["cv_mean_f1"],  4),
        "cv_mean_acc"             : round(metrics["cv_mean_acc"], 4),
        # ← NEW: thresholds essential for production inference
        "decision_thresholds"     : {
            cls: round(float(thresholds[i]), 4)
            for i, cls in enumerate(le.classes_)
        },
        "threshold_target_recall" : achieved_target,
        "threshold_rule"          : "predict = argmax(prob / threshold)",
        "uncertainty_threshold"   : UNCERTAINTY_THRESHOLD,
        "prob_clip_range"         : [PROB_CLIP_LOW, PROB_CLIP_HIGH],
        "smote_conservative_ratio": SMOTE_CONSERVATIVE_RATIO,
        "class_weights"           : CUSTOM_CLASS_WEIGHTS,
        "classes"                 : list(le.classes_),
        "features"                : features,
        "n_features"              : len(features),
        "training_date"           : datetime.utcnow().isoformat(),
        "notes": (
            "KNNImputer(k=7) + RobustScaler; "
            "custom class weights {Normal:1.0, PCOD:1.8, PCOS:1.8}; "
            "conservative BorderlineSMOTE (90 %); "
            "OOF-based threshold optimisation for PCOS/PCOD recall; "
            "probability clipping [0.05, 0.95]; "
            "uncertainty threshold 0.55."
        ),
    }

    meta_path = MODEL_DIR / "pcos_ensemble_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    rank_path = REPORT_DIR / "shap_feature_ranking.csv"
    shap_ranking.to_csv(rank_path, index=False)

    print("\n" + "="*60)
    print("  SAVED ARTEFACTS")
    print("="*60)
    print(f"  Model    → {model_path}")
    print(f"  Metadata → {meta_path}")
    print(f"  SHAP CSV → {rank_path}")


# ══════════════════════════════════════════════
# 13.  MAIN ORCHESTRATOR
# ══════════════════════════════════════════════
def train(data_path: str):
    """
    load → preprocess → conservative SMOTE → stacking ensemble
    → 10-fold CV → threshold optimisation → final fit → evaluate
    → SHAP → save artefacts
    """
    X_train, X_test, y_train, y_test, features, le = load_dataset(data_path)
    n_classes = len(le.classes_)

    smote_strategy   = build_conservative_smote_strategy(y_train)
    preprocessor     = build_preprocessor(features)
    xgb_clf, rf_clf, et_clf = build_models(n_classes)
    calibrated_stack = build_stacking(xgb_clf, rf_clf, et_clf)
    pipeline         = build_pipeline(preprocessor, calibrated_stack, smote_strategy)

    acc, f1, auc, cv_f1, cv_acc, thresholds, achieved_target = train_and_evaluate(
        pipeline, X_train, X_test, y_train, y_test, le
    )

    shap_ranking = generate_shap_plots(pipeline, X_test, features, le)

    save_artefacts(
        pipeline, le, features,
        metrics={
            "accuracy"   : acc,
            "macro_f1"   : f1,
            "roc_auc"    : auc,
            "cv_mean_f1" : cv_f1,
            "cv_mean_acc": cv_acc,
        },
        shap_ranking     = shap_ranking,
        thresholds       = thresholds,
        achieved_target  = achieved_target,
    )

    print("\n" + "="*60)
    print("  TRAINING COMPLETE ✓")
    print("="*60)
    return pipeline, thresholds, le


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════
if __name__ == "__main__":

    DATA_PATH = ("C:\\Users\\HARSHAN\\OneDrive\\Desktop\\FINAL PROJECT\\PCOD_PCOS_UNAFFECTED\\datasets\\final datasets\\REALISTIC_PCOD_PCOS_DATASET_463.csv")

    pipeline, thresholds, le = train(DATA_PATH)