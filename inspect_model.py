# inspect_model.py
import joblib, json, numpy as np, pandas as pd, sys
print("Loading model and meta...")
m = joblib.load("models/pcos_pipeline.joblib")
meta = json.load(open("models/pcos_pipeline.meta.json"))
print("Model type:", type(m))
print("Has predict_proba:", hasattr(m, "predict_proba"))
print("Model attributes (short):", [k for k in dir(m) if not k.startswith("_")][:40])
print("meta keys:", list(meta.keys()))
features = meta.get("features")
print("features:", features)
# two distinct test rows
# Build rows safely using feature names
row1 = {f: 0 for f in features}
row2 = {f: 0 for f in features}

# Example realistic inputs
row1.update({
    "Age": 25,
    "BMI": 21.0,
    "Length_of_cycle": 28,
    "Length_of_menses": 5,
    "Length_of_Leutal_Phase": 14,
    "Estimated_day_of_ovulation": 14,
    "Mean_of_length_of_cycle": 28,
    "height_cm": 160,
    "number_of_peak": 2,
    "weight_kg": 55,
    "Unusual_Bleeding": 0
})

row2.update({
    "Age": 40,
    "BMI": 33.0,
    "Length_of_cycle": 40,
    "Length_of_menses": 7,
    "Length_of_Leutal_Phase": 12,
    "Estimated_day_of_ovulation": 16,
    "Mean_of_length_of_cycle": 36,
    "height_cm": 155,
    "number_of_peak": 1,
    "weight_kg": 70,
    "Unusual_Bleeding": 1
})

X1 = pd.DataFrame([row1])[features]
X2 = pd.DataFrame([row2])[features]

if hasattr(m, "named_steps"):
    print("Pipeline steps:", m.named_steps.keys())
    
try:
    p1 = m.predict_proba(X1)[0]
    p2 = m.predict_proba(X2)[0]
    print("probs1:", p1)
    print("probs2:", p2)
    print("sum1, sum2:", p1.sum(), p2.sum())
except Exception as e:
    print("predict_proba error:", e)
    # try to inspect inner classifier if pipeline
    try:
        inner = m.named_steps.get("clf") if hasattr(m, "named_steps") else None
        print("inner clf:", type(inner), getattr(inner, "get_params", lambda: None)())
    except Exception:
        pass