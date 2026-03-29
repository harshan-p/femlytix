# app.py  — UI-redesigned version with ELITE EMAIL AUTHENTICATION
# AUTH CHANGES: email verification OTP · lockout · password reset · strength check
# All other logic (ML, PDF, charts, screening tabs) is UNCHANGED.

import re
import sqlite3
from datetime import datetime, timedelta          # ← added timedelta
from pathlib import Path
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from pdf_report import generate_prioritized_pdf
import bcrypt
import joblib

# ── NEW: elite auth helpers ──────────────────────────────────
from auth_email import (
    generate_otp,
    otp_expiry,
    is_expired,
    send_verification_email,
    send_password_reset_email,
)

# ============================================================
# PREMIUM UI CSS — injected before anything else
# ============================================================
GLOBAL_CSS = """
<style>
/* ── Google Fonts ──────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

/* ── Tokens ─────────────────────────────────────────────────── */
:root {
  --bg-base:       #050c1a;
  --bg-surface:    #081120;
  --card-bg:       rgba(255,255,255,0.042);
  --card-border:   rgba(255,255,255,0.10);
  --card-border-h: rgba(0,212,200,0.35);
  --teal:          #00d4c8;
  --teal-dim:      rgba(0,212,200,0.15);
  --teal-glow:     0 0 28px rgba(0,212,200,0.28);
  --rose:          #ff6b8a;
  --rose-dim:      rgba(255,107,138,0.15);
  --purple:        #7c6fcd;
  --text-hi:       #e8f0fe;
  --text-mid:      #94a3b8;
  --text-lo:       #4a5568;
  --normal:        #22c55e;
  --normal-bg:     rgba(34,197,94,0.14);
  --pcod:          #f59e0b;
  --pcod-bg:       rgba(245,158,11,0.14);
  --pcos:          #f43f5e;
  --pcos-bg:       rgba(244,63,94,0.14);
  --radius-card:   18px;
  --radius-btn:    50px;
  --font-main:     'DM Sans', sans-serif;
  --font-display:  'DM Serif Display', serif;
  --shadow-card:   0 8px 40px rgba(0,0,0,0.45);
  --transition:    0.24s cubic-bezier(0.34,1.26,0.64,1);
}

/* ── Base reset ─────────────────────────────────────────────── */
html, body, .stApp, .main, .block-container {
  font-family: var(--font-main) !important;
  background: var(--bg-base) !important;
  color: var(--text-hi) !important;
  -webkit-user-select: none !important;
  user-select: none !important;
  caret-color: transparent !important;
}
input, textarea, select,
.stTextInput input, .stNumberInput input,
.stTextArea textarea {
  -webkit-user-select: text !important;
  user-select: text !important;
  caret-color: auto !important;
}

/* Animated mesh background */
.stApp::before {
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 15% 10%,  rgba(0,212,200,0.07) 0%, transparent 65%),
    radial-gradient(ellipse 60% 40% at 85% 80%,  rgba(124,111,205,0.10) 0%, transparent 60%),
    radial-gradient(ellipse 50% 50% at 50% 50%,  rgba(255,107,138,0.04) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* ── Block container ───────────────────────────────────────── */
.block-container {
  padding: 1.5rem 2.5rem 4rem !important;
  max-width: 1140px !important;
}

/* ── Headings ─────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-display) !important;
  color: var(--text-hi) !important;
}

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(175deg, #060d1c 0%, #0c1628 60%, #0d1430 100%) !important;
  border-right: 1px solid var(--card-border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-mid) !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: var(--text-hi) !important;
}

/* ── Glass card ────────────────────────────────────────────── */
.glass-card {
  background: var(--card-bg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card);
  padding: 2rem 2.2rem;
  margin-bottom: 1.4rem;
  box-shadow: var(--shadow-card);
  transition: border-color var(--transition), box-shadow var(--transition);
  animation: fadeSlideUp 0.55s both;
}
.glass-card:hover {
  border-color: var(--card-border-h);
  box-shadow: var(--shadow-card), var(--teal-glow);
}

/* ── Animations ─────────────────────────────────────────────── */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(22px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulseTeal {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0,212,200,0.4); }
  50%       { box-shadow: 0 0 0 10px rgba(0,212,200,0); }
}
@keyframes shimmer {
  0%   { background-position: -600px 0; }
  100% { background-position:  600px 0; }
}
@keyframes scanLine {
  0%   { top: -4%; }
  100% { top: 104%; }
}
@keyframes gradBg {
  0%  { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100%{ background-position: 0% 50%; }
}

/* ── Hero banner ───────────────────────────────────────────── */
.hero-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 4rem 3.5rem;
  margin-bottom: 2.5rem;
  background: linear-gradient(135deg, #060f22 0%, #0d1f40 40%, #0a1a35 70%, #101525 100%);
  border: 1px solid rgba(0,212,200,0.18);
  box-shadow: 0 16px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06);
  animation: fadeSlideUp 0.7s both;
}
.hero-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 60% at 80% 40%, rgba(0,212,200,0.12) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 10% 70%, rgba(124,111,205,0.14) 0%, transparent 60%);
  pointer-events: none;
}
/* Scan line effect */
.hero-wrap::after {
  content: '';
  position: absolute;
  left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(0,212,200,0.5), transparent);
  animation: scanLine 4s linear infinite;
  pointer-events: none;
}
.hero-overline {
  font-family: var(--font-main) !important;
  font-size: 11px;
  letter-spacing: 3.5px;
  text-transform: uppercase;
  color: var(--teal) !important;
  margin-bottom: 1rem;
  font-weight: 600;
}
.hero-title {
  font-family: var(--font-display) !important;
  font-size: clamp(2.2rem, 4vw, 3.4rem) !important;
  line-height: 1.15 !important;
  color: var(--text-hi) !important;
  margin: 0 0 1rem !important;
}
.hero-title span {
  background: linear-gradient(90deg, var(--teal), #a5f3f0, var(--rose));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  background-size: 200% auto;
  animation: gradBg 4s ease infinite;
}
.hero-sub {
  font-size: 1.05rem;
  color: var(--text-mid) !important;
  max-width: 560px;
  line-height: 1.65;
  margin-bottom: 2rem;
}
.trust-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 1.6rem;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-main);
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  padding: 7px 15px;
  border-radius: 50px;
  border: 1px solid;
}
.badge-teal  { color: var(--teal);   border-color: rgba(0,212,200,0.3);  background: rgba(0,212,200,0.08); }
.badge-rose  { color: var(--rose);   border-color: rgba(255,107,138,0.3); background: rgba(255,107,138,0.08); }
.badge-blue  { color: #7dd3fc;       border-color: rgba(125,211,252,0.3); background: rgba(125,211,252,0.08); }
.badge-green { color: var(--normal); border-color: rgba(34,197,94,0.3);   background: rgba(34,197,94,0.08); }

/* ── Feature grid (Why Choose) ─────────────────────────────── */
.feat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin: 1.8rem 0;
}
.feat-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 1.6rem 1.5rem;
  transition: border-color 0.2s, transform 0.2s;
  animation: fadeSlideUp 0.6s both;
}
.feat-card:hover { border-color: var(--card-border-h); transform: translateY(-4px); }
.feat-icon { font-size: 2rem; margin-bottom: 0.8rem; display: block; }
.feat-title {
  font-family: var(--font-main) !important;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-hi) !important;
  margin-bottom: 0.4rem;
}
.feat-desc { font-size: 0.85rem; color: var(--text-mid) !important; line-height: 1.55; }

/* ── Step progress tracker ─────────────────────────────────── */
.step-tracker {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 1.4rem 0 2rem;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.step-dot {
  width: 42px; height: 42px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
  font-weight: 700;
  border: 2px solid var(--card-border);
  background: var(--card-bg);
  color: var(--text-lo);
  transition: all 0.3s;
}
.step-dot.active {
  border-color: var(--teal);
  background: var(--teal-dim);
  color: var(--teal);
  animation: pulseTeal 1.8s ease infinite;
}
.step-dot.done {
  border-color: var(--normal);
  background: rgba(34,197,94,0.14);
  color: var(--normal);
}
.step-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--text-lo);
  text-transform: uppercase;
}
.step-label.active { color: var(--teal) !important; }
.step-label.done   { color: var(--normal) !important; }
.step-line {
  width: 80px; height: 2px;
  background: var(--card-border);
  margin: 0 6px 18px;
  border-radius: 2px;
  transition: background 0.3s;
}
.step-line.done { background: var(--normal); }
.step-line.active { background: linear-gradient(90deg, var(--normal), var(--teal)); }

/* ── Section header ─────────────────────────────────────────── */
.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1.6rem;
}
.section-icon {
  width: 44px; height: 44px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
  background: var(--teal-dim);
  border: 1px solid rgba(0,212,200,0.2);
}
.section-title {
  font-family: var(--font-display) !important;
  font-size: 1.6rem !important;
  color: var(--text-hi) !important;
  margin: 0 !important;
}
.section-sub {
  font-size: 0.8rem;
  color: var(--text-mid) !important;
  margin: 0;
}

/* ── Input styling ──────────────────────────────────────────── */
.stNumberInput input,
.stTextInput input,
.stSelectbox select {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--card-border) !important;
  border-radius: 10px !important;
  color: var(--text-hi) !important;
  font-family: var(--font-main) !important;
  padding: 10px 14px !important;
  transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stNumberInput input:focus,
.stTextInput input:focus {
  border-color: var(--teal) !important;
  box-shadow: 0 0 0 3px rgba(0,212,200,0.12) !important;
  outline: none !important;
}
label, .stNumberInput label,
.stTextInput label,
.stSelectbox label {
  color: var(--text-mid) !important;
  font-size: 0.82rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.3px !important;
  font-family: var(--font-main) !important;
}

/* ── Gradient buttons ────────────────────────────────────────── */
.stButton > button {
  font-family: var(--font-main) !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  letter-spacing: 0.3px !important;
  border-radius: var(--radius-btn) !important;
  padding: 11px 28px !important;
  border: none !important;
  background: linear-gradient(135deg, var(--teal) 0%, #00b8a4 60%, #00a5e0 100%) !important;
  color: #05111f !important;
  box-shadow: 0 4px 20px rgba(0,212,200,0.30) !important;
  transition: transform 0.18s, box-shadow 0.18s !important;
  cursor: pointer !important;
}
.stButton > button:hover {
  transform: translateY(-2px) scale(1.02) !important;
  box-shadow: 0 8px 30px rgba(0,212,200,0.45) !important;
}
.stButton > button:active {
  transform: translateY(0) scale(0.99) !important;
}
/* Logout button — secondary ghost style */
[data-testid="stHorizontalBlock"] .stButton:last-child > button,
button[kind="secondary"] {
  background: transparent !important;
  border: 1px solid var(--card-border) !important;
  color: var(--text-mid) !important;
  box-shadow: none !important;
}
[data-testid="stHorizontalBlock"] .stButton:last-child > button:hover {
  border-color: var(--rose) !important;
  color: var(--rose) !important;
  box-shadow: 0 0 12px rgba(255,107,138,0.2) !important;
}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: rgba(255,255,255,0.03) !important;
  border-radius: 50px !important;
  padding: 5px !important;
  border: 1px solid var(--card-border) !important;
  gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 40px !important;
  padding: 9px 22px !important;
  font-family: var(--font-main) !important;
  font-weight: 600 !important;
  font-size: 0.84rem !important;
  color: var(--text-mid) !important;
  background: transparent !important;
  border: none !important;
  transition: all 0.22s !important;
}
.stTabs [aria-selected="true"] {
  background: linear-gradient(135deg, var(--teal-dim), rgba(0,165,224,0.15)) !important;
  color: var(--teal) !important;
  border: 1px solid rgba(0,212,200,0.22) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }

/* ── Divider ─────────────────────────────────────────────────── */
hr { border-color: var(--card-border) !important; margin: 1.8rem 0 !important; }

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: rgba(0,212,200,0.25); border-radius: 10px; }

/* ── About page cards ─────────────────────────────────────────── */
.about-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 1.5rem 1.8rem;
  margin-bottom: 1.2rem;
  border-left: 3px solid var(--teal);
  animation: fadeSlideUp 0.5s both;
}
.about-card-pcos { border-left-color: var(--pcos); }
.about-card-pcod { border-left-color: var(--pcod); }
.about-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 50px;
  margin-bottom: 0.7rem;
}
.about-tag-teal  { background: var(--teal-dim);  color: var(--teal); }
.about-tag-rose  { background: var(--pcos-bg);   color: var(--pcos); }
.about-tag-amber { background: var(--pcod-bg);   color: var(--pcod); }

/* ── Auth cards ──────────────────────────────────────────────── */
.auth-wrap {
  max-width: 500px;
}
.auth-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-lo) !important;
  margin-bottom: 0.3rem;
}

/* ── Result display ──────────────────────────────────────────── */
.result-badge {
  border-radius: 20px;
  padding: 2.4rem 2.6rem;
  text-align: center;
  position: relative;
  overflow: hidden;
  animation: fadeSlideUp 0.6s both;
}
.result-badge::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.06), transparent);
  pointer-events: none;
}
.result-badge-normal { background: var(--normal-bg); border: 1.5px solid rgba(34,197,94,0.35); }
.result-badge-pcod   { background: var(--pcod-bg);   border: 1.5px solid rgba(245,158,11,0.35); }
.result-badge-pcos   { background: var(--pcos-bg);   border: 1.5px solid rgba(244,63,94,0.35); }
.result-icon-big { font-size: 3rem; display: block; margin-bottom: 0.5rem; }
.result-diagnosis {
  font-family: var(--font-display) !important;
  font-size: 2rem !important;
  margin-bottom: 0.3rem !important;
}
.result-conf {
  font-size: 1.1rem;
  font-weight: 700;
  margin-bottom: 0.6rem;
}
.result-note { font-size: 0.82rem; color: rgba(255,255,255,0.7) !important; line-height: 1.5; }

/* Confidence meter */
.conf-meter-wrap { margin: 1rem 0; }
.conf-meter-track {
  height: 8px;
  border-radius: 50px;
  background: rgba(255,255,255,0.08);
  overflow: hidden;
  margin-top: 6px;
}
.conf-meter-fill {
  height: 100%;
  border-radius: 50px;
  transition: width 1s cubic-bezier(0.34,1.26,0.64,1);
}

/* ── AI Loading ───────────────────────────────────────────────── */
.ai-loading {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 2rem;
  text-align: center;
}
.shimmer-bar {
  height: 8px;
  border-radius: 50px;
  background: linear-gradient(90deg, var(--card-bg) 25%, rgba(0,212,200,0.2) 50%, var(--card-bg) 75%);
  background-size: 600px 100%;
  animation: shimmer 1.4s infinite;
  margin: 0.5rem 0;
}

/* ── Trust block ─────────────────────────────────────────────── */
.trust-block {
  background: linear-gradient(135deg, rgba(0,212,200,0.05) 0%, rgba(0,165,224,0.08) 100%);
  border: 1px solid rgba(0,212,200,0.15);
  border-radius: 16px;
  padding: 1.4rem 1.8rem;
  margin-top: 1.6rem;
  animation: fadeSlideUp 0.7s both;
}
.trust-items {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 0.8rem;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-mid) !important;
}
.trust-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--teal); flex-shrink: 0; }

/* ── Disclaimer card ─────────────────────────────────────────── */
.disclaimer-card {
  background: rgba(255,107,138,0.06);
  border: 1px solid rgba(255,107,138,0.18);
  border-radius: 14px;
  padding: 1rem 1.4rem;
  font-size: 0.8rem;
  color: var(--text-mid) !important;
  line-height: 1.6;
  margin-top: 1.2rem;
}

/* ── Sidebar pills ───────────────────────────────────────────── */
.sidebar-pill {
  background: rgba(0,212,200,0.07);
  border: 1px solid rgba(0,212,200,0.15);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 12px;
  color: var(--text-mid);
  line-height: 1.55;
  margin-bottom: 10px;
}
.sidebar-pill strong { color: var(--teal) !important; display: block; margin-bottom: 3px; font-size: 11px; letter-spacing: 0.5px; text-transform: uppercase; }

/* ── Footer ───────────────────────────────────────────────────── */
.footer-wrap {
  border-top: 1px solid var(--card-border);
  margin-top: 3rem;
  padding-top: 1.4rem;
  text-align: center;
  font-size: 12px;
  color: var(--text-lo) !important;
  line-height: 1.7;
  animation: fadeSlideUp 0.8s both;
}
.footer-logo {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: var(--teal) !important;
  margin-bottom: 0.4rem;
}

/* ── Table styling ────────────────────────────────────────────── */
[data-testid="stTable"] table {
  background: transparent !important;
  border-radius: 12px;
  overflow: hidden;
}
[data-testid="stTable"] th {
  background: rgba(0,212,200,0.08) !important;
  color: var(--teal) !important;
  font-weight: 700 !important;
  font-size: 12px !important;
  letter-spacing: 0.5px !important;
  text-transform: uppercase !important;
  border-bottom: 1px solid var(--card-border) !important;
}
[data-testid="stTable"] td {
  color: var(--text-mid) !important;
  font-size: 13px !important;
  border-bottom: 1px solid rgba(255,255,255,0.04) !important;
  background: transparent !important;
}
[data-testid="stTable"] tr:hover td { background: rgba(0,212,200,0.04) !important; }

/* ── Download button ─────────────────────────────────────────── */
.stDownloadButton > button {
  background: linear-gradient(135deg, rgba(0,212,200,0.15), rgba(0,165,224,0.15)) !important;
  border: 1px solid rgba(0,212,200,0.3) !important;
  color: var(--teal) !important;
  font-weight: 700 !important;
  border-radius: var(--radius-btn) !important;
  padding: 11px 28px !important;
}
.stDownloadButton > button:hover {
  background: linear-gradient(135deg, rgba(0,212,200,0.25), rgba(0,165,224,0.25)) !important;
  box-shadow: 0 4px 20px rgba(0,212,200,0.25) !important;
}

/* ── Selectbox ───────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--card-border) !important;
  border-radius: 10px !important;
  color: var(--text-hi) !important;
}

/* ── Number input spinners ────────────────────────────────────── */
.stNumberInput [data-testid="stNumberInputContainer"] {
  background: rgba(255,255,255,0.05) !important;
  border-radius: 10px !important;
  border: 1px solid var(--card-border) !important;
}
.stNumberInput button {
  background: transparent !important;
  border: none !important;
  color: var(--teal) !important;
  box-shadow: none !important;
}

/* ── Spinner ──────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: var(--teal) !important; }

/* ── Plotly chart bg ─────────────────────────────────────────── */
.js-plotly-plot .plotly, .plot-container { background: transparent !important; }

/* ── OTP input — large & centered ───────────────────────────── */
.otp-field input {
  font-size: 2rem !important;
  letter-spacing: 10px !important;
  text-align: center !important;
  font-family: 'Courier New', monospace !important;
  font-weight: 800 !important;
  color: var(--teal) !important;
  background: rgba(0,212,200,0.06) !important;
  border-color: rgba(0,212,200,0.3) !important;
}

/* ── Password-strength bar ───────────────────────────────────── */
.pw-strength-wrap { margin: 4px 0 10px; }
.pw-strength-track {
  height: 5px; border-radius: 50px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}
.pw-strength-fill { height: 100%; border-radius: 50px; transition: width 0.4s, background 0.4s; }
</style>
"""

# ============================================================
# HELPERS: HTML snippets (UNCHANGED)
# ============================================================

def hero_html():
    return """
<div class="hero-wrap">
  <p class="hero-overline">⚕  AI Screening Platform · v1.0</p>
  <h1 class="hero-title">
    F E M L Y T I X
  </h1>
  <p class="hero-sub">
    AI-DRIVEN PCOS & PCOD PREDICTION BEYOND CLINICAL BOUNDARIES
  </p>
  <div class="trust-badges">
    <span class="badge badge-teal">🧠 AI-Powered Analysis</span>
    <span class="badge badge-blue">🔒 Secure &amp; Private</span>
    <span class="badge badge-green">🏥 Clinical Support Tool</span>
    <span class="badge badge-rose">⚡ Instant Results</span>
  </div>
</div>
"""

def feature_grid_html():
    return """
<div class="feat-grid">
  <div class="feat-card" style="animation-delay:0.05s">
    <span class="feat-icon">🤖</span>
    <p class="feat-title">XGBoost ML Engine</p>
    <p class="feat-desc">Developed a machine learning model using menstrual health parameters for high-confidence 3-way classification.</p>
  </div>
  <div class="feat-card" style="animation-delay:0.12s">
    <span class="feat-icon">🧬</span>
    <p class="feat-title">No Lab Tests Needed</p>
    <p class="feat-desc">Non-invasive screening driven entirely by menstrual history and lifestyle data — no blood draws required.</p>
  </div>
  <div class="feat-card" style="animation-delay:0.20s">
    <span class="feat-icon">📊</span>
    <p class="feat-title">Probability Breakdown</p>
    <p class="feat-desc">Transparent confidence scores across PCOS, PCOD and Normal profiles with downloadable medical report.</p>
  </div>
</div>
"""

def step_tracker_html(active: int):
    """active: 0=Personal, 1=Menstrual, 2=Result"""
    def dot_cls(i):
        if i < active:  return "done"
        if i == active: return "active"
        return ""
    def lbl_cls(i):
        if i < active:  return "done"
        if i == active: return "active"
        return ""
    def line_cls(i):
        if i < active:  return "done"
        if i == active: return "active"
        return ""
    steps = [("👤","Personal Info"), ("📋","Health Data"), ("🔮","AI Results")]
    html = '<div class="step-tracker">'
    for i, (icon, lbl) in enumerate(steps):
        dc = dot_cls(i); lc = lbl_cls(i)
        html += f'<div class="step-item"><div class="step-dot {dc}">{icon}</div><span class="step-label {lc}">{lbl}</span></div>'
        if i < len(steps)-1:
            lnc = line_cls(i)
            html += f'<div class="step-line {lnc}"></div>'
    html += '</div>'
    return html

def section_header_html(icon, title, sub=""):
    sub_html = f'<p class="section-sub">{sub}</p>' if sub else ""
    return f"""
<div class="section-header">
  <div class="section-icon">{icon}</div>
  <div>
    <h2 class="section-title">{title}</h2>
    {sub_html}
  </div>
</div>
"""

def result_badge_html(label, color_cls, icon, conf_pct):
    fill_color = {"result-badge-normal": "#22c55e", "result-badge-pcod": "#f59e0b", "result-badge-pcos": "#f43f5e"}.get(color_cls, "#00d4c8")
    return f"""
<div class="result-badge {color_cls}">
  <span class="result-icon-big">{icon}</span>
  <p class="result-diagnosis" style="color:{'#22c55e' if 'normal' in color_cls else '#f59e0b' if 'pcod' in color_cls else '#f43f5e'}">{label}</p>
  <p class="result-conf" style="color:rgba(255,255,255,0.9)">Confidence Score: {conf_pct:.1f}%</p>
  <div class="conf-meter-wrap">
    <div class="conf-meter-track">
      <div class="conf-meter-fill" style="width:{conf_pct:.1f}%; background: linear-gradient(90deg, {fill_color}aa, {fill_color});"></div>
    </div>
  </div>
  <p class="result-note">AI screening result based on your inputs.<br>Please consult a qualified gynaecologist for clinical confirmation.</p>
</div>
"""

def trust_block_html():
    return """
<div class="trust-block">
  <p style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--teal);margin-bottom:0.2rem;">🔐 Privacy &amp; Security</p>
  <div class="trust-items">
    <span class="trust-item"><span class="trust-dot"></span> Data encrypted at rest</span>
    <span class="trust-item"><span class="trust-dot"></span> No data shared with third parties</span>
    <span class="trust-item"><span class="trust-dot"></span> BCRYPT password hashing</span>
    <span class="trust-item"><span class="trust-dot"></span> Email-verified accounts only</span>
    <span class="trust-item"><span class="trust-dot"></span> Brute-force lockout protection</span>
    <span class="trust-item"><span class="trust-dot"></span> Screening tool — not a medical device</span>
  </div>
</div>
"""

def disclaimer_html(small=False):
    size = "0.75rem" if small else "0.8rem"
    return f"""
<div class="disclaimer-card" style="font-size:{size}">
  ⚠️ <strong style="color:var(--rose)">Disclaimer:</strong>&nbsp;
  This platform is an early-screening tool only and does not constitute a medical diagnosis.
  Results should be interpreted by a licensed healthcare professional.
  Never delay or disregard professional medical advice based on information from this tool.
</div>
"""

def footer_html():
    return """
<div class="footer-wrap">
  <p class="footer-logo">FEMLYTIX · Menstrual Screening Platform</p>
  <p>Built for clinical support &amp; early detection </p>
</div>
"""

# ─────────────────────────────────────────────────────────────
# NEW: Auth UI snippets
# ─────────────────────────────────────────────────────────────

def _pw_strength(pw: str) -> tuple[int, str, str]:
    """Returns (score 0-4, label, color)."""
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 12: score += 1
    if re.search(r"[A-Z]", pw): score += 1
    if re.search(r"[0-9]", pw): score += 1
    if re.search(r"[^A-Za-z0-9]", pw): score += 1
    score = min(score, 4)
    labels = ["Too short", "Weak", "Fair", "Good", "Strong"]
    colors = ["#f43f5e", "#f59e0b", "#eab308", "#22c55e", "#00d4c8"]
    return score, labels[score], colors[score]

def pw_strength_html(pw: str) -> str:
    score, label, color = _pw_strength(pw)
    pct = int(score / 4 * 100)
    return f"""
<div class="pw-strength-wrap">
  <div class="pw-strength-track">
    <div class="pw-strength-fill" style="width:{pct}%;background:{color};"></div>
  </div>
  <p style="font-size:11px;color:{color};margin:3px 0 0;font-weight:600;">{label}</p>
</div>"""

def auth_alert(msg: str, kind: str = "error") -> str:
    """kind: error | success | info | warning"""
    cfg = {
        "error":   ("❌", "rgba(244,63,94,0.08)",  "rgba(244,63,94,0.25)",  "#f43f5e"),
        "success": ("✅", "rgba(34,197,94,0.08)",  "rgba(34,197,94,0.25)",  "#22c55e"),
        "info":    ("ℹ️", "rgba(0,212,200,0.08)",  "rgba(0,212,200,0.25)",  "#00d4c8"),
        "warning": ("⚠️", "rgba(245,158,11,0.08)", "rgba(245,158,11,0.25)", "#f59e0b"),
    }
    ico, bg, border, color = cfg.get(kind, cfg["error"])
    return f"""
<div style="background:{bg};border:1px solid {border};border-radius:12px;
            padding:0.85rem 1.2rem;margin-top:0.8rem;font-size:0.82rem;
            color:{color};line-height:1.55;animation:fadeSlideUp 0.3s both;">
  {ico}&nbsp; {msg}
</div>"""

# ----------------------------
# Configuration (UNCHANGED)
# ----------------------------
MODEL_PATH = Path("models/pcos_pipeline.joblib")
META_PATH  = Path("models/pcos_pipeline.meta.json")
DB_PATH    = "pcos_app.db"

st.set_page_config(page_title="FEMLYTIX · Menstrual Screening", page_icon="🩺", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ----------------------------
# Feature builder (UNCHANGED)
# ----------------------------
def build_features(personal, menstrual):
    eps = 1e-6
    age        = personal.get("Age", 25)
    bmi        = personal.get("bmi", 22)
    cycle      = menstrual.get("Length_of_cycle", 28)
    menses     = menstrual.get("Length_of_menses", 5)
    luteal     = menstrual.get("Length_of_Leutal_Phase", 14)
    ovulation  = menstrual.get("Estimated_day_of_ovulation", 14)
    mean_cycle = menstrual.get("Mean_of_length_of_cycle", 28)
    peaks      = menstrual.get("number_of_peak", 2)

    feats = {}
    feats["Age"]                    = age
    feats["BMI"]                    = bmi
    feats["Length_of_cycle"]        = cycle
    feats["Length_of_menses"]       = menses
    feats["Length_of_Leutal_Phase"] = luteal
    feats["Estimated_day_of_ovulation"] = ovulation
    feats["Mean_of_length_of_cycle"]= mean_cycle
    feats["number_of_peak"]         = peaks
    feats["Cycle_Irregularity"]     = abs(cycle - mean_cycle)
    feats["Ovulation_Ratio"]        = ovulation / (cycle + eps)
    feats["Luteal_Ratio"]           = luteal / (cycle + eps)
    feats["Peak_Density"]           = peaks / (cycle + eps)
    feats["BMI_Age_Interaction"]    = bmi * age
    feats["High_BMI_Flag"]          = int(bmi >= 27)
    feats["Very_Irregular_Cycle"]   = int(cycle > 40)
    feats["Ovulation_Problem"]      = int(abs(ovulation - 14) > 4)
    feats["Long_Menses_Flag"]       = int(menses > 7)
    return feats

# ============================================================
# DATABASE  —  ENHANCED SCHEMA (auth columns added)
# ============================================================
def init_db(path=DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False)
    cur  = conn.cursor()

    # Users table — full elite schema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            email                   TEXT UNIQUE,
            name                    TEXT,
            password_hash           TEXT,
            created_at              TEXT,
            is_verified             INTEGER DEFAULT 0,
            verification_otp        TEXT,
            verification_otp_expiry TEXT,
            failed_attempts         INTEGER DEFAULT 0,
            locked_until            TEXT,
            reset_otp               TEXT,
            reset_otp_expiry        TEXT,
            last_login              TEXT
        )""")

    # Migration guard: add new columns to existing databases
    _migrations = [
        "ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN verification_otp TEXT",
        "ALTER TABLE users ADD COLUMN verification_otp_expiry TEXT",
        "ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN locked_until TEXT",
        "ALTER TABLE users ADD COLUMN reset_otp TEXT",
        "ALTER TABLE users ADD COLUMN reset_otp_expiry TEXT",
        "ALTER TABLE users ADD COLUMN last_login TEXT",
    ]
    for sql in _migrations:
        try:
            cur.execute(sql)
        except Exception:
            pass  # column already exists

    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, email TEXT, timestamp TEXT,
            personal_json TEXT, menstrual_json TEXT,
            prediction TEXT, confidence REAL
        )""")
    conn.commit()
    return conn

conn = init_db()

# ============================================================
# AUTH HELPERS — ENHANCED
# ============================================================

# ── Password hashing (UNCHANGED) ──
def hash_password(pw):    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def verify_password(pw, h):
    try:    return bcrypt.checkpw(pw.encode(), h.encode())
    except: return False

# ── Registration — now sends verification email ──
def save_user(email: str, name: str, password: str) -> tuple[bool, str | None, str | None]:
    """
    Returns (ok, error, warning).
    warning is set when account created but email sending failed.
    """
    otp    = generate_otp()
    expiry = otp_expiry(minutes=15)
    cur    = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO users
               (email, name, password_hash, created_at,
                is_verified, verification_otp, verification_otp_expiry)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (email, name, hash_password(password),
             datetime.utcnow().isoformat(), otp, expiry))
        conn.commit()
    except sqlite3.IntegrityError:
        return False, "This email is already registered.", None

    ok, err = send_verification_email(email, name, otp)
    if not ok:
        # Account created but email failed — user can resend
        return True, None, f"Account created, but email delivery failed: {err}"
    return True, None, None

# ── Login — checks verification + brute-force lockout ──
_MAX_ATTEMPTS   = 5
_LOCKOUT_MINUTES = 15

def authenticate(email: str, password: str) -> tuple[bool, dict | None, str | None]:
    """
    Returns (ok, user_dict | None, error | None).
    Special error sentinel "EMAIL_NOT_VERIFIED" signals redirect to OTP screen.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id, password_hash, name, is_verified, failed_attempts, locked_until "
        "FROM users WHERE email=?", (email,))
    row = cur.fetchone()

    if not row:
        return False, None, "No account found with this email."

    uid, pw_hash, name, is_verified, failed_attempts, locked_until = row
    failed_attempts = failed_attempts or 0

    # ── Lockout check ──
    if locked_until:
        try:
            lock_dt = datetime.fromisoformat(locked_until)
            if datetime.utcnow() < lock_dt:
                mins_left = max(1, int((lock_dt - datetime.utcnow()).total_seconds() / 60) + 1)
                return False, None, (
                    f"🔒 Account temporarily locked. "
                    f"Try again in {mins_left} minute{'s' if mins_left != 1 else ''}."
                )
            else:
                # Lockout expired — reset counter
                cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (uid,))
                conn.commit()
                failed_attempts = 0
        except Exception:
            pass

    # ── Password check ──
    if not verify_password(password, pw_hash):
        failed_attempts += 1
        if failed_attempts >= _MAX_ATTEMPTS:
            lock_until = (datetime.utcnow() + timedelta(minutes=_LOCKOUT_MINUTES)).isoformat()
            cur.execute(
                "UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                (failed_attempts, lock_until, uid))
            conn.commit()
            return False, None, (
                f"🔒 Too many failed attempts. "
                f"Account locked for {_LOCKOUT_MINUTES} minutes."
            )
        cur.execute("UPDATE users SET failed_attempts=? WHERE id=?", (failed_attempts, uid))
        conn.commit()
        remaining = _MAX_ATTEMPTS - failed_attempts
        return False, None, (
            f"Incorrect password. "
            f"{remaining} attempt{'s' if remaining != 1 else ''} remaining before lockout."
        )

    # ── Email verification gate ──
    if not is_verified:
        # Return user info so we can pre-fill the verify screen
        return False, {"id": uid, "email": email, "name": name}, "EMAIL_NOT_VERIFIED"

    # ── Success ──
    cur.execute(
        "UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=? WHERE id=?",
        (datetime.utcnow().isoformat(), uid))
    conn.commit()
    return True, {"id": uid, "email": email, "name": name}, None

# ── Email OTP verification ──
def verify_email_otp(email: str, otp: str) -> tuple[bool, str | None]:
    cur = conn.cursor()
    cur.execute(
        "SELECT verification_otp, verification_otp_expiry FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row:
        return False, "User not found."
    stored_otp, expiry = row
    if not stored_otp:
        return False, "No pending verification code. Please request a new one."
    if is_expired(expiry):
        return False, "Code has expired (15-minute window). Click 'Resend Code'."
    if otp.strip() != stored_otp:
        return False, "Incorrect code. Please check your email and try again."
    cur.execute(
        "UPDATE users SET is_verified=1, verification_otp=NULL, verification_otp_expiry=NULL "
        "WHERE email=?", (email,))
    conn.commit()
    return True, None

# ── Resend verification OTP ──
def resend_verification_otp(email: str) -> tuple[bool, str | None]:
    cur = conn.cursor()
    cur.execute("SELECT name, is_verified FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row:
        return False, "User not found."
    name, is_verified = row
    if is_verified:
        return False, "This account is already verified. Please sign in."
    otp    = generate_otp()
    expiry = otp_expiry(minutes=15)
    cur.execute(
        "UPDATE users SET verification_otp=?, verification_otp_expiry=? WHERE email=?",
        (otp, expiry, email))
    conn.commit()
    ok, err = send_verification_email(email, name, otp)
    if not ok:
        return False, f"Email delivery failed: {err}"
    return True, None

# ── Password reset — request ──
def request_password_reset(email: str) -> tuple[bool, str | None]:
    cur = conn.cursor()
    cur.execute("SELECT name, is_verified FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    # Always return success to prevent email enumeration
    if not row or not row[1]:
        return True, None
    name = row[0]
    otp    = generate_otp()
    expiry = otp_expiry(minutes=15)
    cur.execute(
        "UPDATE users SET reset_otp=?, reset_otp_expiry=? WHERE email=?",
        (otp, expiry, email))
    conn.commit()
    ok, err = send_password_reset_email(email, name, otp)
    if not ok:
        return False, f"Email delivery failed: {err}"
    return True, None

# ── Password reset — confirm ──
def reset_password_with_otp(email: str, otp: str, new_password: str) -> tuple[bool, str | None]:
    cur = conn.cursor()
    cur.execute("SELECT reset_otp, reset_otp_expiry FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row:
        return False, "User not found."
    stored_otp, expiry = row
    if not stored_otp:
        return False, "No reset request found. Please request a new code."
    if is_expired(expiry):
        return False, "Code has expired. Please request a new one."
    if otp.strip() != stored_otp:
        return False, "Incorrect reset code."
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."
    cur.execute(
        """UPDATE users SET
           password_hash=?, reset_otp=NULL, reset_otp_expiry=NULL,
           failed_attempts=0, locked_until=NULL
           WHERE email=?""",
        (hash_password(new_password), email))
    conn.commit()
    return True, None

# ── Submission save (UNCHANGED) ──
def save_submission(user, personal, menstrual, prediction, confidence):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO submissions (user_id,email,timestamp,personal_json,menstrual_json,prediction,confidence) VALUES(?,?,?,?,?,?,?)",
        (user.get("id") if user else None,
         user.get("email") if user else personal.get("email"),
         datetime.utcnow().isoformat(),
         json.dumps(personal), json.dumps(menstrual),
         prediction, float(confidence)))
    conn.commit()

# ----------------------------
# Rerun / logout helpers (UNCHANGED logic)
# ----------------------------
def safe_rerun():
    try:    st.experimental_rerun()
    except: st.session_state["_force_rerun_flag"] = not st.session_state.get("_force_rerun_flag", False)

def logout_user_cb():
    keys = [
        "logged_in","user","about_done","show_register","personal_inputs","menstrual_inputs",
        "last_result","active_section","_open_tab_index","active_tab","login_email","login_pw",
        "reg_name","reg_email","reg_pw","reg_pw2",
        # new auth state keys
        "show_verify_otp","verify_email_addr","pending_reg_name",
        "show_forgot_pw","show_reset_pw","reset_email_addr",
        "verify_otp_input","forgot_email_input","reset_otp_input",
        "reset_new_pw","reset_new_pw2",
    ]
    for k in keys:
        if k in st.session_state: del st.session_state[k]
    st.session_state["logged_in"]  = False
    st.session_state["about_done"] = False
    st.session_state["user"]       = None
    try:    st.experimental_rerun()
    except: st.session_state["_force_reload"] = True

# ----------------------------
# Load model & metadata (UNCHANGED)
# ----------------------------
model = None; meta = {}
if MODEL_PATH.exists():
    try:    model = joblib.load(str(MODEL_PATH))
    except: model = None
if META_PATH.exists():
    try:
        with open(META_PATH) as f: meta = json.load(f)
    except: meta = {}

label_classes = meta.get("label_classes") if isinstance(meta, dict) else None

def map_model_classes_to_strings(classes):
    mapped = []
    for c in classes:
        try:
            if label_classes is not None and (isinstance(c,(int,np.integer)) or str(c).isdigit()):
                idx = int(c)
                if 0 <= idx < len(label_classes):
                    mapped.append(label_classes[idx]); continue
        except: pass
        mapped.append(str(c))
    return mapped

# ----------------------------
# Utilities (UNCHANGED)
# ----------------------------
def height_to_cm(h):
    try:    s = str(h).strip()
    except: return 160.0
    m = re.match(r"^\s*(\d+)\s*[\'\s]\s*(\d+(\.\d+)?)", s)
    if m: return round(float(m.group(1))*30.48 + float(m.group(2))*2.54, 1)
    m2 = re.match(r"^\s*(\d+(\.\d+)?)\s*(cm)?\s*$", s, flags=re.I)
    if m2:
        val = float(m2.group(1))
        if val <= 12: return round(val*30.48, 1)
        return round(val, 1)
    try:
        val = float(re.sub(r"[^\d\.]","",s))
        if val <= 12:  return round(val*30.48, 1)
        if val <= 84:  return round(val*2.54,  1)
        return round(val, 1)
    except: return 160.0

def bmi_category(bmi):
    if bmi < 18.5: return "Underweight"
    if bmi < 25:   return "Normal"
    if bmi < 30:   return "Overweight"
    return "Obese"

def fallback_predict(personal, menstrual):
    score  = 0.0
    lc     = float(menstrual.get("Length_of_cycle") or 28)
    bmi    = float(personal.get("bmi") or 22)
    unusual= int(menstrual.get("Unusual_Bleeding") or 0)
    if lc > 35:   score += 0.35
    if bmi >= 30: score += 0.20
    if unusual:   score += 0.10
    if score > 0.6: return "PCOS_Positive", min(0.99, score)
    if score > 0.3: return "PCOD_Positive", min(0.95, score)
    return "Normal Profile", max(0.05, 1-score)

# ============================================================
# SESSION STATE DEFAULTS  —  extended for new auth flows
# ============================================================
_defaults = [
    ("logged_in",        False),
    ("about_done",       False),
    ("user",             None),
    ("show_register",    False),
    ("active_section",   "personal"),
    ("personal_inputs",  {}),
    ("menstrual_inputs", {}),
    ("last_result",      None),
    # ── NEW auth state ──
    ("show_verify_otp",  False),
    ("verify_email_addr",""),
    ("pending_reg_name", ""),
    ("show_forgot_pw",   False),
    ("show_reset_pw",    False),
    ("reset_email_addr", ""),
]
for k, v in _defaults:
    if k not in st.session_state:
        st.session_state[k] = v

# ----------------------------
# Sidebar (UNCHANGED)
# ----------------------------
def render_sidebar_content():
    user = st.session_state.get("user") or {}
    st.sidebar.markdown("""
<div style="padding:1.4rem 0.5rem 0.8rem; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:1.2rem;">
  <p style="font-family:'DM Serif Display',serif; font-size:1.35rem; color:#00d4c8; margin:0 0 2px;">FEMLYTIX</p>
  <p style="font-size:11px; color:#4a5568; letter-spacing:1px; text-transform:uppercase; margin:0;">Menstrual Screening Platform</p>
</div>
""", unsafe_allow_html=True)
    if user.get("name"):
        st.sidebar.markdown(f"""
<div class="sidebar-pill">
  <strong>👤 Logged in as</strong>
  {user.get('name','')}<br>
  <span style="font-size:11px;color:#4a5568;">{user.get('email','')}</span>
</div>
""", unsafe_allow_html=True)
    st.sidebar.markdown("""
<div class="sidebar-pill" style="margin-top:1rem;">
  <strong>🎓 About This Project</strong>
  Final Year B.E. BME<br>
  XGBoost · Streamlit · SQLite
</div>
<div class="sidebar-pill">
  <strong>👥 Development Team</strong>
  Harshan P &nbsp;·&nbsp; Ramzan Begam A &nbsp;·&nbsp; Sureka S
</div>
<div class="sidebar-pill">
  <strong>📊 Model Stats</strong>
  3-class XGBoost pipeline<br>
  Hormonal + menstrual biomarkers
</div>
""", unsafe_allow_html=True)
    st.sidebar.markdown("""
<div style="margin-top:auto; padding-top:1.5rem; border-top:1px solid rgba(255,255,255,0.06); font-size:11px; color:#2d3748; text-align:center;">
  ⚕️ Not a diagnostic device<br>Consult a healthcare provider
</div>
""", unsafe_allow_html=True)

# ============================================================
# BUTTON CALLBACKS  —  auth ones are enhanced/new
# ============================================================

# ── Existing screening callbacks (UNCHANGED) ──
def do_start_screening():
    st.session_state["about_done"]    = True
    st.session_state["active_section"]= "personal"
    safe_rerun()

def do_personal_next():
    age    = st.session_state.get("age_input", 25)
    height = st.session_state.get("height_input","5'4")
    weight = st.session_state.get("weight_input", 55.0)
    h_cm   = height_to_cm(height)
    try:    bmi = weight / ((h_cm/100)**2)
    except: bmi = 0.0
    st.session_state["personal_inputs"] = {
        "Age": int(age), "height_cm": round(h_cm,1),
        "height_raw": height, "weight_kg": round(weight,1), "bmi": round(bmi,2)}
    st.session_state["active_section"] = "menstrual"
    safe_rerun()

def do_menstrual_back():
    st.session_state["active_section"] = "personal"
    safe_rerun()

def do_menstrual_next():
    st.session_state["menstrual_inputs"] = {
        "number_of_peak":           int(st.session_state.get("number_of_peak_input",2)),
        "Length_of_cycle":          int(st.session_state.get("length_cycle_input",28)),
        "Length_of_menses":         int(st.session_state.get("length_menses_input",5)),
        "Unusual_Bleeding":         1 if st.session_state.get("unusual_bleeding_input","No")=="Yes" else 0,
        "Length_of_Leutal_Phase":   int(st.session_state.get("luteal_input",14)),
        "Estimated_day_of_ovulation": int(st.session_state.get("ovulation_input",14)),
        "Mean_of_length_of_cycle":  int(st.session_state.get("mean_cycle_input",28)),
    }
    st.session_state["active_section"] = "result"
    safe_rerun()

def do_result_back():
    st.session_state["active_section"] = "menstrual"
    safe_rerun()

# ── ENHANCED: Login — handles lockout + unverified gate ──
def do_login():
    email = st.session_state.get("login_email","").strip().lower()
    pw    = st.session_state.get("login_pw","")
    if not email or not pw:
        st.session_state["_login_error"] = "Please enter both email and password."; return
    ok, user, err = authenticate(email, pw)
    if ok:
        st.session_state["logged_in"]      = True
        st.session_state["user"]           = user
        st.session_state["about_done"]     = False
        st.session_state["active_section"] = "personal"
        safe_rerun()
    elif err == "EMAIL_NOT_VERIFIED":
        # Redirect to OTP screen instead of showing an error
        st.session_state["show_verify_otp"]  = True
        st.session_state["verify_email_addr"] = email
        if user:
            st.session_state["pending_reg_name"] = user.get("name", "")
        safe_rerun()
    else:
        st.session_state["_login_error"] = err

def do_show_register():
    st.session_state["show_register"]  = True
    st.session_state["show_forgot_pw"] = False
    st.session_state["show_reset_pw"]  = False
    safe_rerun()

# ── ENHANCED: Registration — validates strength + sends OTP ──
def do_create_account():
    name  = st.session_state.get("reg_name","").strip()
    email = st.session_state.get("reg_email","").strip().lower()
    pw    = st.session_state.get("reg_pw","")
    pw2   = st.session_state.get("reg_pw2","")

    if not name or not email or not pw:
        st.session_state["_reg_error"] = "Please fill in all fields."; return
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        st.session_state["_reg_error"] = "Please enter a valid email address."; return
    if pw != pw2:
        st.session_state["_reg_error"] = "Passwords do not match."; return
    if len(pw) < 8:
        st.session_state["_reg_error"] = "Password must be at least 8 characters."; return

    ok, err, warning = save_user(email, name, pw)
    if ok:
        st.session_state["show_register"]    = False
        st.session_state["show_verify_otp"]  = True
        st.session_state["verify_email_addr"]= email
        st.session_state["pending_reg_name"] = name
        for k in ("reg_name","reg_email","reg_pw","reg_pw2"):
            st.session_state[k] = ""
        if warning:
            st.session_state["_verify_warning"] = warning
    else:
        st.session_state["_reg_error"] = err
    safe_rerun()

def do_cancel_register():
    st.session_state["show_register"] = False
    for k in ("reg_name","reg_email","reg_pw","reg_pw2"):
        if k in st.session_state: del st.session_state[k]
    safe_rerun()

# ── NEW: OTP verification callbacks ──
def do_verify_otp():
    email = st.session_state.get("verify_email_addr","")
    otp   = st.session_state.get("verify_otp_input","").strip()
    if not otp:
        st.session_state["_verify_error"] = "Please enter the 6-digit code."; return
    ok, err = verify_email_otp(email, otp)
    if ok:
        st.session_state["show_verify_otp"]  = False
        st.session_state["verify_email_addr"]= ""
        st.session_state["_reg_success"]     = "Email verified! Your account is active. Sign in below."
        safe_rerun()
    else:
        st.session_state["_verify_error"] = err

def do_resend_otp():
    email = st.session_state.get("verify_email_addr","")
    ok, err = resend_verification_otp(email)
    if ok:
        st.session_state["_verify_warning"] = "New code sent — check your inbox (and spam folder)."
    else:
        st.session_state["_verify_error"] = err
    safe_rerun()

def do_back_to_login():
    st.session_state["show_verify_otp"] = False
    st.session_state["show_forgot_pw"]  = False
    st.session_state["show_reset_pw"]   = False
    st.session_state["verify_email_addr"]= ""
    st.session_state["reset_email_addr"] = ""
    safe_rerun()

# ── NEW: Password reset callbacks ──
def do_show_forgot_pw():
    st.session_state["show_forgot_pw"] = True
    st.session_state["show_register"]  = False
    safe_rerun()

def do_send_reset_otp():
    email = st.session_state.get("forgot_email_input","").strip().lower()
    if not email:
        st.session_state["_forgot_error"] = "Please enter your email address."; return
    ok, err = request_password_reset(email)
    if ok:
        st.session_state["show_forgot_pw"]  = False
        st.session_state["show_reset_pw"]   = True
        st.session_state["reset_email_addr"]= email
        st.session_state["_reset_info"]     = (
            "If this email is registered and verified, a reset code has been sent. "
            "Check your inbox (and spam folder)."
        )
        safe_rerun()
    else:
        st.session_state["_forgot_error"] = err

def do_reset_password():
    email = st.session_state.get("reset_email_addr","")
    otp   = st.session_state.get("reset_otp_input","").strip()
    pw    = st.session_state.get("reset_new_pw","")
    pw2   = st.session_state.get("reset_new_pw2","")
    if not otp or not pw or not pw2:
        st.session_state["_reset_error"] = "Please fill in all fields."; return
    if pw != pw2:
        st.session_state["_reset_error"] = "Passwords do not match."; return
    ok, err = reset_password_with_otp(email, otp, pw)
    if ok:
        st.session_state["show_reset_pw"]   = False
        st.session_state["reset_email_addr"]= ""
        st.session_state["_reg_success"]    = "Password reset successfully! You can now sign in."
        safe_rerun()
    else:
        st.session_state["_reset_error"] = err

# ── Screening predict callbacks (UNCHANGED) ──
def predict_from_widgets():
    age_w    = st.session_state.get("age_input")
    height_w = st.session_state.get("height_input")
    weight_w = st.session_state.get("weight_input")
    sp       = st.session_state.get("personal_inputs",{})
    age_v    = age_w    if age_w    is not None else sp.get("Age",25)
    h_raw    = height_w if height_w is not None else sp.get("height_raw","5'4")
    weight_v = weight_w if weight_w is not None else sp.get("weight_kg",55.0)
    h_cm     = height_to_cm(h_raw)
    try:    bmi_v = float(weight_v)/((h_cm/100)**2)
    except: bmi_v = sp.get("bmi",21.48)
    st.session_state["personal_inputs"] = {
        "Age": int(age_v), "height_cm": round(h_cm,1),
        "height_raw": h_raw, "weight_kg": float(weight_v), "bmi": round(bmi_v,2)}
    sm = st.session_state.get("menstrual_inputs",{})
    ub_w = st.session_state.get("unusual_bleeding_input")
    ub_v = (1 if ub_w=="Yes" else 0) if ub_w is not None else sm.get("Unusual_Bleeding",0)
    def _mi(key, def_key, default):
        v = st.session_state.get(key)
        return int(v) if v is not None else int(sm.get(def_key, default))
    st.session_state["menstrual_inputs"] = {
        "number_of_peak":           _mi("number_of_peak_input","number_of_peak",2),
        "Length_of_cycle":          _mi("length_cycle_input","Length_of_cycle",28),
        "Length_of_menses":         _mi("length_menses_input","Length_of_menses",5),
        "Unusual_Bleeding":         int(ub_v),
        "Length_of_Leutal_Phase":   _mi("luteal_input","Length_of_Leutal_Phase",14),
        "Estimated_day_of_ovulation": _mi("ovulation_input","Estimated_day_of_ovulation",14),
        "Mean_of_length_of_cycle":  _mi("mean_cycle_input","Mean_of_length_of_cycle",28),
    }
    do_predict()

def do_predict():
    personal_saved  = st.session_state.get("personal_inputs",{})
    menstrual_saved = st.session_state.get("menstrual_inputs",{})
    height_cm = height_to_cm(personal_saved.get("height_raw","5'4"))
    try:    bmi_val = float(personal_saved.get("weight_kg",55.0))/((height_cm/100)**2)
    except: bmi_val = personal_saved.get("bmi",21.48)
    personal = {**personal_saved, "height_cm": round(height_cm,1), "bmi": round(bmi_val,2)}
    ub_widget = st.session_state.get("unusual_bleeding_input")
    ub_val    = (1 if ub_widget=="Yes" else 0) if ub_widget is not None else menstrual_saved.get("Unusual_Bleeding",0)
    def _ms(wk, sk, default):
        v = st.session_state.get(wk)
        return int(v) if v is not None else int(menstrual_saved.get(sk, default))
    menstrual = {
        "number_of_peak":           _ms("number_of_peak_input","number_of_peak",2),
        "Length_of_cycle":          _ms("length_cycle_input","Length_of_cycle",28),
        "Length_of_menses":         _ms("length_menses_input","Length_of_menses",5),
        "Unusual_Bleeding":         int(ub_val),
        "Length_of_Leutal_Phase":   _ms("luteal_input","Length_of_Leutal_Phase",14),
        "Estimated_day_of_ovulation": _ms("ovulation_input","Estimated_day_of_ovulation",14),
        "Mean_of_length_of_cycle":  _ms("mean_cycle_input","Mean_of_length_of_cycle",28),
    }
    feature_dict  = build_features(personal, menstrual)
    feature_order = meta.get("features")
    X_input       = pd.DataFrame([[feature_dict.get(f,0) for f in feature_order]], columns=feature_order)
    numeric_defaults = {"Age":25,"BMI":22.0,"Length_of_cycle":28,"Length_of_menses":5,
                        "Length_of_Leutal_Phase":14,"Estimated_day_of_ovulation":14,
                        "Mean_of_length_of_cycle":28,"height_cm":160.0,"number_of_peak":2,
                        "weight_kg":55.0,"Unusual_Bleeding":0}
    for c in X_input.columns:
        X_input[c] = pd.to_numeric(X_input[c], errors="coerce")
        if pd.isna(X_input.at[0,c]):
            X_input.at[0,c] = numeric_defaults.get(c, 0.0)
    if model is not None:
        try:
            probs         = model.predict_proba(X_input)[0]
            classes       = list(model.classes_)
            mapped_classes= map_model_classes_to_strings(classes)
            idx           = int(np.argmax(probs))
            pred_label    = mapped_classes[idx]
            confidence_frac = float(probs[idx])
        except:
            pred_label, confidence_frac = fallback_predict(personal, menstrual)
            probs = None; mapped_classes = None
    else:
        pred_label, confidence_frac = fallback_predict(personal, menstrual)
        probs = None; mapped_classes = None
    try:
        save_submission(st.session_state.get("user",{}), personal, menstrual,
                        str(pred_label), float(confidence_frac))
    except: pass
    st.session_state["last_result"] = {
        "prediction": pred_label, "confidence": confidence_frac,
        "probs": probs, "mapped_classes": mapped_classes,
        "personal": personal, "menstrual": menstrual}
    safe_rerun()

# ============================================================
# MAIN UI
# ============================================================

# ══════════════════════════════════════════════════════════════
# LOGIN / AUTH PAGES
# ══════════════════════════════════════════════════════════════
if not st.session_state["logged_in"]:

    # Always show hero + features at the top
    st.markdown(hero_html(), unsafe_allow_html=True)
    st.markdown(feature_grid_html(), unsafe_allow_html=True)
    st.markdown('<hr style="margin:2rem 0;">', unsafe_allow_html=True)

    # ── BRANCH: which auth panel to show ────────────────────
    show_verify = st.session_state.get("show_verify_otp", False)
    show_forgot = st.session_state.get("show_forgot_pw",  False)
    show_reset  = st.session_state.get("show_reset_pw",   False)

    # ── PANEL 1: Email OTP Verification ─────────────────────
    if show_verify:
        masked_email = st.session_state.get("verify_email_addr","")
        # Mask middle of email for privacy display
        parts = masked_email.split("@")
        if len(parts) == 2 and len(parts[0]) > 2:
            hidden = parts[0][0] + "·"*(len(parts[0])-2) + parts[0][-1]
            display_email = f"{hidden}@{parts[1]}"
        else:
            display_email = masked_email

        col_v, _, _ = st.columns([2, 0.3, 1])
        with col_v:
            st.markdown(f"""
<div class="glass-card" style="text-align:center;padding:2.4rem 2.2rem;">
  <p style="font-size:3rem;margin:0 0 0.5rem">📧</p>
  <p style="font-family:'DM Serif Display',serif;font-size:1.5rem;
            color:var(--text-hi);margin:0 0 0.4rem;">Check Your Inbox</p>
  <p style="font-size:0.82rem;color:var(--text-mid);margin:0 0 0.3rem;line-height:1.6;">
    We sent a <strong style="color:var(--teal)">6-digit code</strong> to
  </p>
  <p style="font-size:0.9rem;font-weight:700;color:var(--teal);
            margin:0 0 1.6rem;letter-spacing:0.5px;">{display_email}</p>
  <p style="font-size:0.75rem;color:var(--text-lo);margin:0 0 1.4rem;">
    Code expires in <strong style="color:#f59e0b;">15 minutes</strong>
    &nbsp;·&nbsp; Check spam if not in inbox
  </p>
""", unsafe_allow_html=True)

            # Large OTP input
            st.markdown('<div class="otp-field">', unsafe_allow_html=True)
            st.text_input(
                "Enter 6-digit code",
                key="verify_otp_input",
                max_chars=6,
                placeholder="  · · · · · ·",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            vb1, vb2 = st.columns(2)
            with vb1:
                st.button("✅  Verify Email", key="verify_otp_btn",
                          on_click=do_verify_otp, use_container_width=True)
            with vb2:
                st.button("📨  Resend Code", key="resend_otp_btn",
                          on_click=do_resend_otp, use_container_width=True)

            if st.session_state.get("_verify_error"):
                st.markdown(auth_alert(st.session_state.pop("_verify_error"), "error"),
                            unsafe_allow_html=True)
            if st.session_state.get("_verify_warning"):
                st.markdown(auth_alert(st.session_state.pop("_verify_warning"), "info"),
                            unsafe_allow_html=True)

            st.markdown('<hr style="margin:1.2rem 0 1rem;">', unsafe_allow_html=True)
            st.markdown(
                '<p style="text-align:center;font-size:0.78rem;color:var(--text-lo);">'
                'Already verified?</p>', unsafe_allow_html=True)
            bc = st.columns([1,2,1])
            with bc[1]:
                st.button("← Back to Sign In", key="verify_back_btn",
                          on_click=do_back_to_login, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)  # close glass-card

    # ── PANEL 2: Forgot Password — enter email ───────────────
    elif show_forgot:
        col_f, _, _ = st.columns([2, 0.3, 1])
        with col_f:
            st.markdown("""
<div class="glass-card" style="padding:2.4rem 2.2rem;">
  <p style="font-size:2.2rem;margin:0 0 0.5rem">🔑</p>
  <p style="font-family:'DM Serif Display',serif;font-size:1.45rem;
            color:var(--text-hi);margin:0 0 0.2rem;">Reset your password</p>
  <p style="font-size:0.8rem;color:var(--text-mid);margin:0 0 1.4rem;line-height:1.6;">
    Enter your registered email. We'll send a 6-digit reset code
    if the account exists and is verified.
  </p>
""", unsafe_allow_html=True)
            st.text_input("📧  Registered email address", key="forgot_email_input")

            fb1, fb2 = st.columns(2)
            with fb1:
                st.button("📨  Send Reset Code", key="send_reset_btn",
                          on_click=do_send_reset_otp, use_container_width=True)
            with fb2:
                st.button("← Back to Sign In", key="forgot_back_btn",
                          on_click=do_back_to_login, use_container_width=True)

            if st.session_state.get("_forgot_error"):
                st.markdown(auth_alert(st.session_state.pop("_forgot_error"), "error"),
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── PANEL 3: Reset Password — enter code + new password ─
    elif show_reset:
        col_r, _, _ = st.columns([2, 0.3, 1])
        with col_r:
            st.markdown("""
<div class="glass-card" style="padding:2.4rem 2.2rem;">
  <p style="font-size:2.2rem;margin:0 0 0.5rem">🔐</p>
  <p style="font-family:'DM Serif Display',serif;font-size:1.45rem;
            color:var(--text-hi);margin:0 0 0.2rem;">Set new password</p>
  <p style="font-size:0.8rem;color:var(--text-mid);margin:0 0 1.2rem;">
    Enter the 6-digit code from your email, then choose a new password.
  </p>
""", unsafe_allow_html=True)

            if st.session_state.get("_reset_info"):
                st.markdown(auth_alert(st.session_state.pop("_reset_info"), "info"),
                            unsafe_allow_html=True)

            st.markdown('<div class="otp-field">', unsafe_allow_html=True)
            st.text_input("🔢  6-digit reset code", key="reset_otp_input",
                          max_chars=6, placeholder="  · · · · · ·")
            st.markdown('</div>', unsafe_allow_html=True)

            rc1, rc2 = st.columns(2)
            with rc1:
                st.text_input("🔒  New password", type="password", key="reset_new_pw")
            with rc2:
                st.text_input("🔒  Confirm password", type="password", key="reset_new_pw2")

            # Show strength meter for new password
            _npw = st.session_state.get("reset_new_pw","")
            if _npw:
                st.markdown(pw_strength_html(_npw), unsafe_allow_html=True)

            rb1, rb2 = st.columns(2)
            with rb1:
                st.button("🔐  Reset Password", key="reset_pw_btn",
                          on_click=do_reset_password, use_container_width=True)
            with rb2:
                st.button("← Back to Sign In", key="reset_back_btn",
                          on_click=do_back_to_login, use_container_width=True)

            if st.session_state.get("_reset_error"):
                st.markdown(auth_alert(st.session_state.pop("_reset_error"), "error"),
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── PANEL 4 (DEFAULT): Login + Register ─────────────────
    else:
        col_login, col_gap, col_info = st.columns([2, 0.2, 1.2])
        with col_login:
            st.markdown("""
<div class="glass-card" style="animation-delay:0.1s">
  <p style="font-family:'DM Serif Display',serif;font-size:1.45rem;
            color:var(--text-hi);margin:0 0 0.2rem;">Welcome back</p>
  <p style="font-size:0.8rem;color:var(--text-mid);margin:0 0 1.4rem;">
    Sign in to access your screening dashboard
  </p>
""", unsafe_allow_html=True)
            st.text_input("📧  Email address", key="login_email")
            st.text_input("🔑  Password", type="password", key="login_pw")

            b1, b2 = st.columns(2)
            with b1:
                st.button("Sign In →", key="login_btn", on_click=do_login,
                          use_container_width=True)
            with b2:
                st.button("Create Account", key="show_register_btn",
                          on_click=do_show_register, use_container_width=True)

            # Forgot password link (styled as a small button row)
            st.markdown(
                '<p style="text-align:right;font-size:0.78rem;margin:0.4rem 0 0;">'
                '<span style="color:var(--text-lo)">Forgot your password?&nbsp;</span></p>',
                unsafe_allow_html=True)
            fp_col = st.columns([3,1.2])
            with fp_col[1]:
                st.button("Reset it →", key="forgot_pw_btn",
                          on_click=do_show_forgot_pw, use_container_width=True)

            # Error / success messages
            if st.session_state.get("_login_error"):
                st.markdown(auth_alert(st.session_state.pop("_login_error"), "error"),
                            unsafe_allow_html=True)
            if st.session_state.get("_reg_success"):
                st.markdown(auth_alert(st.session_state.pop("_reg_success"), "success"),
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_info:
            st.markdown(trust_block_html(), unsafe_allow_html=True)

        # ── Registration form ────────────────────────────────
        if st.session_state["show_register"]:
            st.markdown('<hr style="margin:1.5rem 0;">', unsafe_allow_html=True)
            st.markdown("""
<div class="glass-card" style="max-width:540px">
  <p style="font-family:'DM Serif Display',serif;font-size:1.35rem;
            color:var(--text-hi);margin:0 0 0.2rem;">Create your account</p>
  <p style="font-size:0.8rem;color:var(--text-mid);margin:0 0 1.4rem;">
    Free screening · Secure · Email-verified
  </p>
""", unsafe_allow_html=True)
            st.text_input("👤  Full name", key="reg_name")
            st.text_input("📧  Email address", key="reg_email")

            rc1, rc2 = st.columns(2)
            with rc1:
                st.text_input("🔒  Password (min 8 chars)", type="password", key="reg_pw")
                _rpw = st.session_state.get("reg_pw","")
                if _rpw:
                    st.markdown(pw_strength_html(_rpw), unsafe_allow_html=True)
            with rc2:
                st.text_input("🔒  Confirm password", type="password", key="reg_pw2")

            rb1, rb2 = st.columns(2)
            with rb1:
                st.button("Create Account →", key="create_account_btn",
                          on_click=do_create_account, use_container_width=True)
            with rb2:
                st.button("Cancel", key="cancel_register_btn",
                          on_click=do_cancel_register, use_container_width=True)

            if st.session_state.get("_reg_error"):
                st.markdown(auth_alert(st.session_state.pop("_reg_error"), "error"),
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(disclaimer_html(small=True), unsafe_allow_html=True)
    st.markdown(footer_html(), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# LOGGED IN — all screening logic UNCHANGED
# ══════════════════════════════════════════════════════════════
else:
    render_sidebar_content()

    show_logout = st.session_state.get("about_done", False)
    top_l, top_m, top_r = st.columns([3, 6, 2])
    with top_l:
        user_name = (st.session_state.get("user") or {}).get("name","")
        if user_name:
            st.markdown(f'<p style="margin:0.9rem 0 0;font-size:0.82rem;color:var(--text-mid)">👋 Hello, <strong style="color:var(--teal)">{user_name}</strong></p>', unsafe_allow_html=True)
    with top_r:
        if show_logout:
            st.button("⎋  Logout", key="logout_btn", on_click=logout_user_cb, use_container_width=True)

    # ── ABOUT / DISCLAIMER PAGE ──────────────────────────────
    if not st.session_state.get("about_done", False):
        st.markdown("""
<div style="text-align:center;padding:2.5rem 0 1.5rem;">
  <p style="font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--teal);margin-bottom:0.6rem">Understanding Your Health</p>
  <h1 style="font-family:'DM Serif Display',serif;font-size:2.4rem;color:var(--text-hi);margin:0 0 0.8rem;">What is PCOS &amp; PCOD?</h1>
  <p style="color:var(--text-mid);max-width:550px;margin:0 auto;font-size:0.95rem;line-height:1.65;">Before we screen, take a moment to understand the conditions we detect. Early knowledge is early power.</p>
</div>
""", unsafe_allow_html=True)

        a1, a2 = st.columns(2)
        with a1:
            st.markdown("""
<div class="about-card about-card-pcos">
  <span class="about-tag about-tag-rose">PCOS · Polycystic Ovary Syndrome</span>
  <p style="color:var(--text-hi);font-weight:600;margin:0 0 0.5rem;font-size:1rem;">The more complex hormonal disorder</p>
  <p style="color:var(--text-mid);font-size:0.85rem;line-height:1.65;margin:0">
    A metabolic and hormonal disorder causing elevated androgens, missed periods, acne, and excessive hair growth.
    Linked to insulin resistance — can increase risk of diabetes and cardiovascular disease if untreated.
  </p>
</div>
""", unsafe_allow_html=True)

        with a2:
            st.markdown("""
<div class="about-card about-card-pcod">
  <span class="about-tag about-tag-amber">PCOD · Polycystic Ovary Disease</span>
  <p style="color:var(--text-hi);font-weight:600;margin:0 0 0.5rem;font-size:1rem;">The more manageable variant</p>
  <p style="color:var(--text-mid);font-size:0.85rem;line-height:1.65;margin:0">
    Ovaries release immature eggs that form cysts, causing irregular cycles and weight gain.
    Fertility is usually preserved. Lifestyle changes — diet, exercise — can significantly reduce symptoms.
  </p>
</div>
""", unsafe_allow_html=True)

        st.markdown("""
<div class="glass-card" style="text-align:center;margin-top:0.8rem;padding:1.6rem">
  <p style="font-size:1rem;font-weight:600;color:var(--teal);margin:0 0 0.4rem">🔬 Why Early Screening Matters</p>
  <p style="color:var(--text-mid);font-size:0.87rem;line-height:1.65;max-width:620px;margin:0 auto">
    Early detection enables timely intervention, better symptom management, and significantly reduced risk
    of long-term complications including type-2 diabetes, cardiovascular disease, and infertility.
    Our AI analyses your pattern in seconds — completely non-invasively.
  </p>
</div>
""", unsafe_allow_html=True)

        st.markdown(disclaimer_html(), unsafe_allow_html=True)

        c1, c2, c3 = st.columns([2, 1.4, 2])
        with c2:
            st.button("Begin Screening →", key="start_screening_btn", on_click=do_start_screening, use_container_width=True)

    # ── SCREENING TABS ────────────────────────────────────────
    else:
        sec = st.session_state.get("active_section","personal")
        step_idx = {"personal":0,"menstrual":1,"result":2}.get(sec,0)
        if st.session_state.get("last_result"): step_idx = 2
        st.markdown(step_tracker_html(step_idx), unsafe_allow_html=True)

        tabs = st.tabs(["👤  Personal Info", "📋  Health Data", "🔮  AI Results"])

        # ── TAB 0: PERSONAL ──────────────────────────────────
        with tabs[0]:
            st.markdown(section_header_html("👤", "Personal Details"), unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Age (years)", min_value=10, max_value=80,
                    value=st.session_state.get("personal_inputs",{}).get("Age",25), key="age_input")
            with c2:
                st.text_input("Height (e.g. 5'6 or 162 cm)",
                    value=st.session_state.get("personal_inputs",{}).get("height_raw","5'4"), key="height_input")
                st.number_input("Weight (kg)", min_value=20.0, max_value=200.0,
                    value=st.session_state.get("personal_inputs",{}).get("weight_kg",55.0), step=0.5, key="weight_input")

            h_cm = height_to_cm(st.session_state.get("height_input","5'4"))
            try:    bmi_live = st.session_state.get("weight_input",55.0)/((h_cm/100)**2)
            except: bmi_live = 0.0
            cat   = bmi_category(bmi_live)
            cat_color = {"Underweight":"#7dd3fc","Normal":"#22c55e","Overweight":"#f59e0b","Obese":"#f43f5e"}.get(cat,"#e2e8f0")
            st.markdown(f"""
<div style="background:rgba(0,212,200,0.06);border:1px solid rgba(0,212,200,0.15);border-radius:12px;
            padding:1rem 1.4rem;margin-top:0.8rem;display:flex;align-items:center;gap:1.5rem;">
  <div>
    <p style="font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--teal);margin:0 0 2px">Calculated BMI</p>
    <p style="font-size:2rem;font-weight:700;color:var(--text-hi);margin:0;font-family:'DM Serif Display',serif">{bmi_live:.1f}</p>
  </div>
  <div>
    <span style="display:inline-block;padding:4px 14px;border-radius:50px;font-size:12px;font-weight:700;
                 background:rgba({','.join(str(int(cat_color.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.15);
                 color:{cat_color};border:1px solid {cat_color}44">{cat}</span>
    <p style="font-size:11px;color:var(--text-mid);margin:4px 0 0"></p>
  </div>
</div>
""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── TAB 1: MENSTRUAL ─────────────────────────────────
        with tabs[1]:
            st.markdown(section_header_html("📋", "Menstrual Health Data"), unsafe_allow_html=True)
            c3, c4 = st.columns(2)
            mi = st.session_state.get("menstrual_inputs",{})
            with c3:
                st.number_input("Number of Peak Days", min_value=0, max_value=10, value=mi.get("number_of_peak",2),
                    key="number_of_peak_input", help="Days with strongest fertility signs (clear discharge / positive OPK).")
                st.number_input("Cycle Length (days)", 10, 120, value=mi.get("Length_of_cycle",28),
                    key="length_cycle_input", help="Days from first day of one period to first day of the next.")
                st.number_input("Menses Duration (days)", 1, 20, value=mi.get("Length_of_menses",5),
                    key="length_menses_input", help="Total number of days bleeding lasts.")
                st.selectbox("Unusual Bleeding?", ["No","Yes"],
                    index=1 if mi.get("Unusual_Bleeding",0) else 0,
                    key="unusual_bleeding_input", help="Spotting, mid-cycle bleeding, or very heavy flow.")
            with c4:
                st.number_input("Luteal Phase Length (days)", 1, 30, value=mi.get("Length_of_Leutal_Phase",14),
                    key="luteal_input", help="Phase between ovulation and next period. [Cycle length − Ovulation day]")
                st.number_input("Estimated Day of Ovulation", 1, 50, value=mi.get("Estimated_day_of_ovulation",14),
                    key="ovulation_input", help="Day ovary releases egg. Estimate: [Cycle length − 14]")
                st.number_input("Average Cycle Length (days)", 10, 120, value=mi.get("Mean_of_length_of_cycle",28),
                    key="mean_cycle_input", help="Mean over your last 3–6 cycles.")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("""
<div style="background:rgba(124,111,205,0.08);border:1px solid rgba(124,111,205,0.18);border-radius:12px;
            padding:0.9rem 1.3rem;margin-top:0.2rem;">
  <p style="font-size:11px;color:rgba(167,155,230,0.9);margin:0;line-height:1.6">
    💡 <strong>Tip:</strong> For most accurate results, use data from your last 3 menstrual cycles.
    If irregular, use your best estimates — the AI accounts for cycle variability.
  </p>
</div>
""", unsafe_allow_html=True)

        # ── TAB 2: RESULTS ────────────────────────────────────
        with tabs[2]:
            st.markdown(section_header_html("🔮", "AI Prediction Results"), unsafe_allow_html=True)

            personal  = st.session_state.get("personal_inputs",  {"Age":25,"height_cm":160.0,"weight_kg":55.0,"bmi":21.48})
            menstrual = st.session_state.get("menstrual_inputs",  {"number_of_peak":2,"Length_of_cycle":28,"Length_of_menses":5,
                                                                    "Unusual_Bleeding":0,"Length_of_Leutal_Phase":14,
                                                                    "Estimated_day_of_ovulation":14,"Mean_of_length_of_cycle":28})

            bc1, bc2, bc3 = st.columns([1,1.4,1])
            with bc2:
                st.button("🤖  Run AI Analysis", key="predict_btn", on_click=predict_from_widgets, use_container_width=True)

            if not st.session_state.get("last_result"):
                st.markdown("""
<div class="glass-card" style="text-align:center;padding:3rem 2rem;margin-top:1rem">
  <p style="font-size:3rem;margin:0 0 0.8rem">🔬</p>
  <p style="font-family:'DM Serif Display',serif;font-size:1.3rem;color:var(--text-hi);margin:0 0 0.4rem">Ready to Analyse</p>
  <p style="color:var(--text-mid);font-size:0.85rem;margin:0">
    Fill in Personal Info and Health Data tabs, then click <strong style="color:var(--teal)">Run AI Analysis</strong> above.
  </p>
</div>
""", unsafe_allow_html=True)
            else:
                res           = st.session_state["last_result"]
                pred          = res["prediction"]
                conf          = res["confidence"]
                personal      = res.get("personal",{})
                menstrual     = res.get("menstrual",{})
                probs         = res.get("probs")
                mapped_classes= res.get("mapped_classes")

                label_map = {
                    "Normal Profile": ("Normal Profile",  "result-badge-normal", "✅"),
                    "PCOD_Positive":  ("PCOD Detected",   "result-badge-pcod",   "❗"),
                    "PCOS_Positive":  ("PCOS Detected",   "result-badge-pcos",   "⚠️"),
                    "Normal":         ("Normal Profile",  "result-badge-normal", "✅"),
                    "PCOD":           ("PCOD Detected",   "result-badge-pcod",   "❗"),
                    "PCOS":           ("PCOS Detected",   "result-badge-pcos",   "⚠️"),
                }
                if pred in label_map:
                    result_label, result_cls, result_icon = label_map[pred]
                else:
                    result_label, result_cls, result_icon = str(pred), "result-badge-normal", "ℹ️"

                conf_pct = conf * 100 if isinstance(conf,(int,float)) and conf <= 1.0 else float(conf)

                st.markdown(result_badge_html(result_label, result_cls, result_icon, conf_pct), unsafe_allow_html=True)

                st.markdown('<p style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text-mid);margin:0 0 1rem">Probability Distribution</p>', unsafe_allow_html=True)

                display_order  = ["Normal Profile","PCOD_Positive","PCOS_Positive"]
                display_names  = ["Normal","PCOD","PCOS"]
                bar_colors     = ["#22c55e","#f59e0b","#f43f5e"]
                prob_map       = {k:0.0 for k in display_order}

                if probs is not None and mapped_classes is not None:
                    for i, cls_label in enumerate(mapped_classes):
                        if cls_label in prob_map:
                            prob_map[cls_label] = float(probs[i])
                        else:
                            s = str(cls_label).lower()
                            if "normal" in s:  prob_map["Normal Profile"]  = float(probs[i])
                            elif "pcod" in s:  prob_map["PCOD_Positive"]   = float(probs[i])
                            elif "pcos" in s:  prob_map["PCOS_Positive"]   = float(probs[i])
                else:
                    mp = pred
                    if pred == "Normal": mp = "Normal Profile"
                    elif pred == "PCOD": mp = "PCOD_Positive"
                    elif pred == "PCOS": mp = "PCOS_Positive"
                    cf = float(conf) if conf <= 1.0 else float(conf)/100.0
                    prob_map[mp] = cf
                    remaining = max(0.0, 1.0 - cf)
                    others = [k for k in display_order if k != mp]
                    for o in others: prob_map[o] += remaining/len(others)

                total = sum(prob_map.values())
                if total > 0:
                    for k in prob_map: prob_map[k] /= total

                y_vals = [prob_map.get(k,0.0)*100 for k in display_order]

                fig = go.Figure(data=[go.Bar(
                    x=display_names, y=y_vals, marker_color=bar_colors,
                    marker=dict(opacity=0.88, line=dict(color="rgba(255,255,255,0.12)", width=1)),
                    text=[f"{v:.1f}%" for v in y_vals], textposition="outside",
                    textfont=dict(color="#94a3b8", size=13, family="DM Sans")
                )])
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans", color="#94a3b8"),
                    yaxis=dict(range=[0,115], title="Probability (%)",
                               gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=11)),
                    xaxis=dict(tickfont=dict(size=13, color="#e2e8f0")),
                    margin=dict(l=10,r=10,t=20,b=10),
                    height=300,
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<p style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text-mid);margin:0 0 1rem">📋 Input Summary</p>', unsafe_allow_html=True)
                summary = [
                    ["Age",               personal.get("Age")],
                    ["Height (cm)",        personal.get("height_cm")],
                    ["Weight (kg)",        personal.get("weight_kg")],
                    ["BMI",               personal.get("bmi")],
                    ["Cycle Length (days)",menstrual.get("Length_of_cycle")],
                    ["Menses Duration",   menstrual.get("Length_of_menses")],
                    ["Luteal Phase",      menstrual.get("Length_of_Leutal_Phase")],
                    ["Ovulation Day",     menstrual.get("Estimated_day_of_ovulation")],
                    ["Mean Cycle Length", menstrual.get("Mean_of_length_of_cycle")],
                    ["Unusual Bleeding",  "Yes" if menstrual.get("Unusual_Bleeding") else "No"],
                    ["Peak Days",         menstrual.get("number_of_peak")],
                ]
                st.table(pd.DataFrame(summary, columns=["Field","Value"]))
                st.markdown('</div>', unsafe_allow_html=True)

                recs = {
                    "diet": [
                        {"text":"Follow a low-glycemic balanced diet.","priority":1,"evidence":"Moderate","rationale":"Helps regulate insulin resistance common in PCOS."},
                        {"text":"Increase fiber intake through vegetables and whole grains.","priority":2,"evidence":"Moderate","rationale":"Improves metabolic health."}
                    ],
                    "exercise":  [{"text":"Engage in 150 minutes/week of moderate exercise.","priority":1,"evidence":"High","rationale":"Improves hormonal balance and weight control."}],
                    "lifestyle": [{"text":"Track menstrual cycle regularly.","priority":1,"evidence":"Limited","rationale":"Helps early detection of abnormalities."}],
                    "medical":   [{"text":"Consult a gynecologist for proper evaluation.","priority":1,"evidence":"High","rationale":"Essential for confirmation and management."}]
                }
                user = st.session_state.get("user") or {}
                pdf_buffer = generate_prioritized_pdf(
                    username=user.get("name","Anonymous"),
                    email=user.get("email",""),
                    inputs={"age":personal.get("Age"),"height_cm":personal.get("height_cm"),
                            "weight":personal.get("weight_kg"),"bmi":personal.get("bmi"),
                            "cycle":menstrual.get("Length_of_cycle"),"menses":menstrual.get("Length_of_menses"),
                            "luteal":menstrual.get("Length_of_Leutal_Phase"),
                            "ovulation":menstrual.get("Estimated_day_of_ovulation"),
                            "unusual":menstrual.get("Unusual_Bleeding")},
                    prediction=pred, confidence=conf*100,
                    probabilities=[prob_map.get("Normal Profile",0),
                                   prob_map.get("PCOD_Positive",0),
                                   prob_map.get("PCOS_Positive",0)],
                    recs=recs)

                st.markdown('<div style="text-align:center;margin-top:1.2rem">', unsafe_allow_html=True)
                st.download_button(
                    "📄  Download Full Medical Report (PDF)",
                    data=pdf_buffer, file_name="Menstrual_Screening_Report.pdf",
                    mime="application/pdf", use_container_width=False)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown(disclaimer_html(small=True), unsafe_allow_html=True)

    st.markdown(footer_html(), unsafe_allow_html=True)

