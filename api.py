"""
api.py — Luna AI × PCOS Screening FastAPI Backend
Wraps the existing joblib stacking pipeline.
Run with: uvicorn api:app --reload --port 8000
"""

import re
import json
import sqlite3
import numpy as np
import pandas as pd
import joblib
import bcrypt

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

import jwt  # pip install pyjwt

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
MODEL_PATH  = Path("models/pcos_pipeline.joblib")
META_PATH   = Path("models/pcos_pipeline.meta.json")
DB_PATH     = "pcos_app.db"
JWT_SECRET  = "CHANGE_THIS_IN_PRODUCTION_TO_A_RANDOM_64_CHAR_STRING"
JWT_ALGO    = "HS256"
JWT_EXPIRE  = 60 * 24  # minutes → 1 day

UNCERTAINTY_THRESHOLD = 0.55
PROB_CLIP_LOW  = 0.05
PROB_CLIP_HIGH = 0.95

# ──────────────────────────────────────────────
# APP + CORS
# ──────────────────────────────────────────────
app = FastAPI(title="Luna AI — PCOS Screening API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ──────────────────────────────────────────────
# DB INIT
# ──────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name  TEXT,
            password_hash TEXT,
            created_at TEXT
        )""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            email      TEXT,
            timestamp  TEXT,
            personal_json  TEXT,
            menstrual_json TEXT,
            prediction TEXT,
            confidence REAL
        )""")
    conn.commit()
    conn.close()

init_db()

# ──────────────────────────────────────────────
# MODEL LOAD
# ──────────────────────────────────────────────
model       = None
meta        = {}
label_classes = None

if MODEL_PATH.exists():
    try:
        model = joblib.load(str(MODEL_PATH))
    except Exception as e:
        print(f"[WARN] Could not load model: {e}")

if META_PATH.exists():
    try:
        with open(META_PATH) as f:
            meta = json.load(f)
        label_classes = meta.get("label_classes") or meta.get("classes")
    except Exception as e:
        print(f"[WARN] Could not load meta: {e}")

# Decision thresholds saved during training (from your train script)
decision_thresholds = meta.get("decision_thresholds", {})  # {class_name: threshold}

# ──────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except:
        return False

def create_token(user_id: int, email: str, name: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return decode_token(creds.credentials)

def optional_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Returns user dict or None — for endpoints that work with or without auth."""
    if not creds:
        return None
    try:
        return decode_token(creds.credentials)
    except:
        return None

# ──────────────────────────────────────────────
# FEATURE ENGINEERING (unchanged from app.py)
# ──────────────────────────────────────────────
def height_to_cm(h) -> float:
    try:
        s = str(h).strip()
    except:
        return 160.0
    m = re.match(r"^\s*(\d+)\s*[\'\s]\s*(\d+(\.\d+)?)", s)
    if m:
        return round(float(m.group(1)) * 30.48 + float(m.group(2)) * 2.54, 1)
    m2 = re.match(r"^\s*(\d+(\.\d+)?)\s*(cm)?\s*$", s, flags=re.I)
    if m2:
        val = float(m2.group(1))
        if val <= 12:
            return round(val * 30.48, 1)
        return round(val, 1)
    try:
        val = float(re.sub(r"[^\d\.]", "", s))
        if val <= 12:  return round(val * 30.48, 1)
        if val <= 84:  return round(val * 2.54, 1)
        return round(val, 1)
    except:
        return 160.0

def build_features(personal: dict, menstrual: dict) -> dict:
    eps = 1e-6
    age      = personal.get("Age",   25)
    bmi      = personal.get("bmi",   22)
    cycle    = menstrual.get("Length_of_cycle",              28)
    menses   = menstrual.get("Length_of_menses",              5)
    luteal   = menstrual.get("Length_of_Leutal_Phase",       14)
    ovul     = menstrual.get("Estimated_day_of_ovulation",   14)
    mean_cyc = menstrual.get("Mean_of_length_of_cycle",      28)
    peaks    = menstrual.get("number_of_peak",                2)

    return {
        "Age"                      : age,
        "BMI"                      : bmi,
        "Length_of_cycle"          : cycle,
        "Length_of_menses"         : menses,
        "Length_of_Leutal_Phase"   : luteal,
        "Estimated_day_of_ovulation": ovul,
        "Mean_of_length_of_cycle"  : mean_cyc,
        "number_of_peak"           : peaks,
        "Cycle_Irregularity"       : abs(cycle - mean_cyc),
        "Ovulation_Ratio"          : ovul   / (cycle + eps),
        "Luteal_Ratio"             : luteal / (cycle + eps),
        "Peak_Density"             : peaks  / (cycle + eps),
        "BMI_Age_Interaction"      : bmi * age,
        "High_BMI_Flag"            : int(bmi >= 27),
        "Very_Irregular_Cycle"     : int(cycle > 40),
        "Ovulation_Problem"        : int(abs(ovul - 14) > 4),
        "Long_Menses_Flag"         : int(menses > 7),
    }

def apply_thresholds(probs: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    """argmax(prob / threshold) — same rule used during training."""
    scaled = probs / thresholds
    return scaled.argmax(axis=1)

def fallback_predict(personal: dict, menstrual: dict):
    score = 0.0
    lc     = float(menstrual.get("Length_of_cycle") or 28)
    bmi    = float(personal.get("bmi") or 22)
    unusual = int(menstrual.get("Unusual_Bleeding") or 0)
    if lc > 35:     score += 0.35
    if bmi >= 30:   score += 0.20
    if unusual:     score += 0.10
    if score > 0.6: return "PCOS_Positive", min(0.99, score)
    if score > 0.3: return "PCOD_Positive", min(0.95, score)
    return "Normal Profile", max(0.05, 1 - score)

def run_inference(personal: dict, menstrual: dict) -> dict:
    """Core inference logic — returns structured result dict."""
    feature_order = meta.get("features")
    feat_dict = build_features(personal, menstrual)

    if model is None or not feature_order:
        pred_label, confidence = fallback_predict(personal, menstrual)
        return {
            "prediction" : pred_label,
            "confidence" : round(float(confidence), 4),
            "probabilities": {
                "Normal Profile": round(float(1 - confidence), 4),
                "PCOD_Positive" : 0.0,
                "PCOS_Positive" : round(float(confidence), 4),
            },
            "uncertain"   : confidence < UNCERTAINTY_THRESHOLD,
            "engine"      : "fallback",
        }

    X = pd.DataFrame(
        [[feat_dict.get(f, 0) for f in feature_order]],
        columns=feature_order
    )
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)

    try:
        raw_probs = model.predict_proba(X)[0]
        classes   = list(label_classes) if label_classes else list(model.classes_)

        # Normalise + clip
        clipped = np.clip(raw_probs, PROB_CLIP_LOW, PROB_CLIP_HIGH)
        probs   = (clipped / clipped.sum()).tolist()

        # Apply per-class decision thresholds if available
        if decision_thresholds:
            thr_arr = np.array([
                decision_thresholds.get(cls, 1.0) for cls in classes
            ])
            pred_idx = int(apply_thresholds(np.array([probs]), thr_arr)[0])
        else:
            pred_idx = int(np.argmax(probs))

        pred_label = classes[pred_idx]
        confidence = float(probs[pred_idx])

        prob_dict  = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}

        # Normalise keys to standard names
        normalised = {}
        for k, v in prob_dict.items():
            kl = k.lower()
            if "normal" in kl:
                normalised["Normal Profile"] = v
            elif "pcod" in kl:
                normalised["PCOD_Positive"] = v
            elif "pcos" in kl:
                normalised["PCOS_Positive"] = v
            else:
                normalised[k] = v

        return {
            "prediction"   : pred_label,
            "confidence"   : round(confidence, 4),
            "probabilities": normalised,
            "uncertain"    : confidence < UNCERTAINTY_THRESHOLD,
            "engine"       : "stacking_ensemble",
        }

    except Exception as e:
        pred_label, confidence = fallback_predict(personal, menstrual)
        return {
            "prediction"   : pred_label,
            "confidence"   : round(float(confidence), 4),
            "probabilities": {"Normal Profile": 0.0, "PCOD_Positive": 0.0, "PCOS_Positive": 0.0},
            "uncertain"    : True,
            "engine"       : f"fallback_error:{e}",
        }

# ──────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ──────────────────────────────────────────────
class RegisterPayload(BaseModel):
    name  : str
    email : str
    password: str

class LoginPayload(BaseModel):
    email   : str
    password: str

class PersonalData(BaseModel):
    Age        : float = 25
    height_raw : str   = "5'4"
    weight_kg  : float = 55.0

class MenstrualData(BaseModel):
    number_of_peak              : int   = 2
    Length_of_cycle             : int   = 28
    Length_of_menses            : int   = 5
    Unusual_Bleeding            : int   = 0
    Length_of_Leutal_Phase      : int   = 14
    Estimated_day_of_ovulation  : int   = 14
    Mean_of_length_of_cycle     : int   = 28

class PredictPayload(BaseModel):
    personal  : PersonalData
    menstrual : MenstrualData

# ──────────────────────────────────────────────
# ROUTES — AUTH
# ──────────────────────────────────────────────
@app.post("/auth/register")
def register(body: RegisterPayload):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email,name,password_hash,created_at) VALUES(?,?,?,?)",
            (body.email.lower(), body.name, hash_pw(body.password),
             datetime.utcnow().isoformat())
        )
        conn.commit()
        uid = cur.lastrowid
        token = create_token(uid, body.email.lower(), body.name)
        return {"token": token, "name": body.name, "email": body.email.lower()}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    finally:
        conn.close()

@app.post("/auth/login")
def login(body: LoginPayload):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT id,password_hash,name FROM users WHERE email=?",
                (body.email.lower(),))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "No account found with that email")
    if not verify_pw(body.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect password")
    token = create_token(row["id"], body.email.lower(), row["name"])
    return {"token": token, "name": row["name"], "email": body.email.lower()}

# ──────────────────────────────────────────────
# ROUTES — PREDICT
# ──────────────────────────────────────────────
@app.post("/predict")
def predict(body: PredictPayload, user=Depends(optional_user)):
    """
    Accepts personal + menstrual data, returns prediction + probabilities.
    Works whether or not the user is authenticated (anonymous mode supported).
    """
    h_cm  = height_to_cm(body.personal.height_raw)
    bmi   = body.personal.weight_kg / ((h_cm / 100) ** 2 + 1e-6)

    personal = {
        "Age"       : int(body.personal.Age),
        "height_cm" : round(h_cm, 1),
        "height_raw": body.personal.height_raw,
        "weight_kg" : round(body.personal.weight_kg, 1),
        "bmi"       : round(bmi, 2),
    }

    menstrual = {
        "number_of_peak"             : body.menstrual.number_of_peak,
        "Length_of_cycle"            : body.menstrual.Length_of_cycle,
        "Length_of_menses"           : body.menstrual.Length_of_menses,
        "Unusual_Bleeding"           : body.menstrual.Unusual_Bleeding,
        "Length_of_Leutal_Phase"     : body.menstrual.Length_of_Leutal_Phase,
        "Estimated_day_of_ovulation" : body.menstrual.Estimated_day_of_ovulation,
        "Mean_of_length_of_cycle"    : body.menstrual.Mean_of_length_of_cycle,
    }

    result = run_inference(personal, menstrual)

    # Save submission if user is authenticated
    if user:
        try:
            conn = get_conn()
            conn.execute(
                """INSERT INTO submissions
                   (user_id,email,timestamp,personal_json,menstrual_json,prediction,confidence)
                   VALUES(?,?,?,?,?,?,?)""",
                (user.get("sub"), user.get("email"),
                 datetime.utcnow().isoformat(),
                 json.dumps(personal), json.dumps(menstrual),
                 result["prediction"], float(result["confidence"]))
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    return {
        **result,
        "personal" : personal,
        "menstrual": menstrual,
        "bmi_category": bmi_category(bmi),
    }

def bmi_category(bmi: float) -> str:
    if bmi < 18.5: return "Underweight"
    if bmi < 25:   return "Normal"
    if bmi < 30:   return "Overweight"
    return "Obese"

# ──────────────────────────────────────────────
# ROUTES — HISTORY (authenticated)
# ──────────────────────────────────────────────
@app.get("/history")
def history(user=Depends(current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT timestamp,prediction,confidence FROM submissions WHERE user_id=? ORDER BY timestamp DESC LIMIT 10",
        (user["sub"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/health")
def health():
    return {
        "status"       : "ok",
        "model_loaded" : model is not None,
        "engine"       : meta.get("model", "unknown"),
        "classes"      : label_classes,
        "features"     : len(meta.get("features", [])),
    }