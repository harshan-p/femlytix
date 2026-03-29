# pdf_report.py — HealthAI · Attractive Infographic Report
# Matches app UI: teal/purple/rose palette, bold cards, clean modern layout

from io import BytesIO
from datetime import datetime
import uuid
import math

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable

# ─────────────────────────────────────────────────────────────
# APP COLOUR TOKENS  (mirrors CSS variables in app.py)
# ─────────────────────────────────────────────────────────────
TEAL        = colors.HexColor("#00D4C8")
TEAL_DARK   = colors.HexColor("#00A89E")
PURPLE      = colors.HexColor("#7C6FCD")
ROSE        = colors.HexColor("#FF6B8A")

NORMAL_GRN  = colors.HexColor("#22C55E")
NORMAL_BG   = colors.HexColor("#EDFAF3")
PCOD_AMB    = colors.HexColor("#F59E0B")
PCOD_BG     = colors.HexColor("#FFF8E6")
PCOS_RED    = colors.HexColor("#F43F5E")
PCOS_BG     = colors.HexColor("#FFF0F2")

NAVY        = colors.HexColor("#050C1A")
TEXT_HI     = colors.HexColor("#1A202C")
TEXT_MID    = colors.HexColor("#4A5568")
TEXT_LO     = colors.HexColor("#94A3B8")
WHITE       = colors.white

PAGE_W, PAGE_H = letter


def _result_tokens(prediction):
    p = str(prediction).lower()
    if "pcos" in p:
        return PCOS_RED,  PCOS_BG,  colors.HexColor("#9F1239"), "PCOS Detected"
    if "pcod" in p:
        return PCOD_AMB,  PCOD_BG,  colors.HexColor("#92400E"), "PCOD Detected"
    return NORMAL_GRN, NORMAL_BG, colors.HexColor("#14532D"),  "Normal Profile"


# ─────────────────────────────────────────────────────────────
# SECTION PILL LABEL
# ─────────────────────────────────────────────────────────────
class SectionPill(Flowable):
    def __init__(self, pw, title, colour):
        super().__init__()
        self.pw  = pw
        self.t   = title
        self.col = colour

    def wrap(self, *_): return self.pw, 26

    def draw(self):
        c   = self.canv
        col = self.col
        bg  = colors.Color(col.red, col.green, col.blue, alpha=0.10)
        c.setFillColor(bg)
        tw = c.stringWidth(self.t, "Helvetica-Bold", 10) + 32
        c.roundRect(0, 4, tw, 20, 6, fill=1, stroke=0)
        c.setFillColor(col)
        c.circle(12, 14, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(TEXT_HI)
        c.drawString(22, 10, self.t)
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.setLineWidth(0.5)
        c.line(0, 3, self.pw, 3)


# ─────────────────────────────────────────────────────────────
# TOP HEADER BANNER
# ─────────────────────────────────────────────────────────────
class TopHeader(Flowable):
    def __init__(self, pw, username, email, report_id, ts):
        super().__init__()
        self.pw       = pw
        self.username = username
        self.email    = email
        self.rid      = report_id
        self.ts       = ts

    def wrap(self, *_): return self.pw, 130

    def draw(self):
        c = self.canv
        w, h = self.pw, 130

        # Navy base
        c.setFillColor(NAVY)
        c.roundRect(0, 0, w, h, 10, fill=1, stroke=0)

        # Teal radial glow top-left
        for r, a in [(90, 0.10), (60, 0.14), (35, 0.18)]:
            c.setFillColor(colors.Color(0, 0.83, 0.78, alpha=a))
            c.circle(-10, h + 10, r, fill=1, stroke=0)

        # Purple glow bottom-right
        for r, a in [(80, 0.10), (50, 0.14)]:
            c.setFillColor(colors.Color(0.49, 0.44, 0.80, alpha=a))
            c.circle(w + 10, -10, r, fill=1, stroke=0)

        # Top teal accent line
        c.setFillColor(TEAL)
        c.roundRect(0, h - 4, w, 4, 2, fill=1, stroke=0)

        # App name
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(WHITE)
        c.drawString(22, h - 34, "FEMLYTIX")

        

        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#A0AEC0"))
        c.drawString(126, h - 34, "PCOS / PCOD Screening Report")

        # Rule
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.10))
        c.setLineWidth(0.5)
        c.line(22, h - 44, w - 22, h - 44)

        # Patient
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(TEAL)
        c.drawString(22, h - 58, "PATIENT")
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(WHITE)
        c.drawString(22, h - 74, self.username or "—")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#718096"))
        c.drawString(22, h - 88, self.email or "—")

        # Report meta right
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#718096"))
        c.drawRightString(w - 22, h - 58, "REPORT ID")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#A0AEC0"))
        c.drawRightString(w - 22, h - 72, self.rid)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#718096"))
        c.drawRightString(w - 22, h - 88, "GENERATED")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#A0AEC0"))
        c.drawRightString(w - 22, h - 102, self.ts)

        # Bottom badges
        badge_data = [
            (TEAL,   "AI-Powered"),
            (PURPLE, "XGBoost Model"),
            (ROSE,   "Non-Clinical Screening"),
        ]
        bx = 22
        for col, lbl in badge_data:
            tw = c.stringWidth(lbl, "Helvetica-Bold", 7) + 18
            c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.18))
            c.roundRect(bx, 10, tw, 16, 4, fill=1, stroke=0)
            c.setFillColor(col)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(bx + 9, 16, lbl)
            bx += tw + 8


# ─────────────────────────────────────────────────────────────
# RESULT HERO CARD
# ─────────────────────────────────────────────────────────────
class ResultHero(Flowable):
    def __init__(self, pw, prediction, confidence):
        super().__init__()
        self.pw         = pw
        self.prediction = prediction
        self.confidence = confidence

    def wrap(self, *_): return self.pw, 140

    def draw(self):
        c = self.canv
        w, h = self.pw, 140
        accent, bg, dark, label = _result_tokens(self.prediction)

        # Card bg
        c.setFillColor(bg)
        c.roundRect(0, 0, w, h, 12, fill=1, stroke=0)

        # Left stripe
        c.setFillColor(accent)
        c.roundRect(0, 0, 10, h, 6, fill=1, stroke=0)
        c.rect(6, 0, 4, h, fill=1, stroke=0)

        # Decorative circles right
        for r, a in [(55, 0.07), (38, 0.11), (24, 0.16)]:
            c.setFillColor(colors.Color(accent.red, accent.green, accent.blue, alpha=a))
            c.circle(w - 50, h / 2, r, fill=1, stroke=0)

        # Icon badge
        c.setFillColor(accent)
        c.circle(36, h - 38, 14, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(WHITE)
        c.drawCentredString(36, h - 44, "Dx")

        # Label
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(dark)
        c.drawString(62, h - 48, label)

        # Sub
        c.setFont("Helvetica", 9)
        c.setFillColor(TEXT_MID)
        c.drawString(62, h - 63, "AI Screening Result  ·  XGBoost Classification  ·  Non-Diagnostic")

        # Divider
        c.setStrokeColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.25))
        c.setLineWidth(0.8)
        c.line(22, h - 74, w - 22, h - 74)

        # Confidence label
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(TEXT_LO)
        c.drawString(22, h - 88, "CONFIDENCE SCORE")

        # Pct
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(dark)
        c.drawString(22, h - 112, f"{self.confidence:.1f}%")

        # Bar
        bx, by, bh = 130, h - 108, 14
        bw = w - bx - 22
        fw = max(bw * min(float(self.confidence) / 100.0, 1.0), 8)
        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.roundRect(bx, by, bw, bh, 5, fill=1, stroke=0)
        c.setFillColor(accent)
        c.roundRect(bx, by, fw, bh, 5, fill=1, stroke=0)
        for pct in [25, 50, 75]:
            tx = bx + bw * pct / 100
            c.setStrokeColor(WHITE)
            c.setLineWidth(1.2)
            c.line(tx, by, tx, by + bh)
            c.setFont("Helvetica", 6)
            c.setFillColor(TEXT_LO)
            c.drawCentredString(tx, by - 9, f"{pct}%")


# ─────────────────────────────────────────────────────────────
# MEASUREMENTS GRID
# ─────────────────────────────────────────────────────────────
class InfoGrid(Flowable):
    FIELDS = [
        ("Age",             "age",           "yrs",  TEAL),
        ("Height",          "height_cm",     "cm",   PURPLE),
        ("Weight",          "weight",        "kg",   colors.HexColor("#06B6D4")),
        ("BMI",             "bmi",           "",     ROSE),
        ("Cycle Length",    "cycle",         "days", NORMAL_GRN),
        ("Menses Duration", "menses",        "days", PCOD_AMB),
        ("Luteal Phase",    "luteal",        "days", PURPLE),
        ("Ovulation Day",   "ovulation",     "",     TEAL),
        ("Unusual Bleeding","unusual_disp",  "",     PCOS_RED),
        ("Mean Cycle",      "mean_cycle",    "days", colors.HexColor("#8B5CF6")),
    ]

    def __init__(self, pw, inputs):
        super().__init__()
        self.pw     = pw
        self.inputs = inputs

    def wrap(self, *_):
        rows = math.ceil(len(self.FIELDS) / 2)
        return self.pw, rows * 52 + 8

    def draw(self):
        c   = self.canv
        w   = self.pw
        cw  = (w - 10) / 2
        ch  = 46
        gap = 10

        for i, (label, key, unit, col) in enumerate(self.FIELDS):
            ci = i % 2
            ri = i // 2
            cx = ci * (cw + gap)
            cy = self.wrap()[1] - (ri + 1) * (ch + 6) + 6

            raw = self.inputs.get(key, "—")
            val = str(raw) if raw not in (None, "") else "—"
            display = f"{val} {unit}".strip() if unit and val != "—" else val

            # Card bg
            c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.08))
            c.roundRect(cx, cy, cw, ch, 7, fill=1, stroke=0)

            # Accent stripe
            c.setFillColor(col)
            c.roundRect(cx, cy, 4, ch, 3, fill=1, stroke=0)
            c.rect(cx + 2, cy, 2, ch, fill=1, stroke=0)

            # Label
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(TEXT_LO)
            c.drawString(cx + 14, cy + ch - 16, label.upper())

            # Value
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(TEXT_HI)
            c.drawString(cx + 14, cy + 8, display)


# ─────────────────────────────────────────────────────────────
# PROBABILITY VISUAL
# ─────────────────────────────────────────────────────────────
class ProbBars(Flowable):
    LABELS  = ["Normal",   "PCOD",   "PCOS"]
    COLOURS = [NORMAL_GRN, PCOD_AMB, PCOS_RED]
    BGS     = [NORMAL_BG,  PCOD_BG,  PCOS_BG]

    def __init__(self, pw, probabilities):
        super().__init__()
        self.pw    = pw
        self.probs = list(probabilities)[:3]
        while len(self.probs) < 3:
            self.probs.append(0.0)

    def wrap(self, *_): return self.pw, 3 * 40 + 12

    def draw(self):
        c  = self.canv
        w  = self.pw
        bh = 16
        row_h = 40

        for i, (label, prob, col, bg) in enumerate(
                zip(self.LABELS, self.probs, self.COLOURS, self.BGS)):
            by = (2 - i) * row_h + 10

            # Row bg
            c.setFillColor(bg)
            c.roundRect(0, by - 2, w, row_h - 4, 7, fill=1, stroke=0)

            # Left colour indicator
            c.setFillColor(col)
            c.roundRect(0, by - 2, 5, row_h - 4, 3, fill=1, stroke=0)
            c.rect(3, by - 2, 2, row_h - 4, fill=1, stroke=0)

            # Label
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(TEXT_HI)
            c.drawString(14, by + bh + 3, label)

            # Pct right
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(col)
            c.drawRightString(w - 8, by + bh + 3, f"{prob * 100:.1f}%")

            # Track
            tx, tw = 90, w - 100 - 60
            c.setFillColor(colors.HexColor("#E2E8F0"))
            c.roundRect(tx, by + 4, tw, bh, 5, fill=1, stroke=0)

            # Fill
            fw = max(tw * min(float(prob), 1.0), 6)
            c.setFillColor(col)
            c.roundRect(tx, by + 4, fw, bh, 5, fill=1, stroke=0)

            # Glow highlight strip on fill
            if fw > 12:
                c.setFillColor(colors.Color(1, 1, 1, alpha=0.18))
                c.roundRect(tx, by + 4 + bh - 5, fw, 5, 3, fill=1, stroke=0)


# ─────────────────────────────────────────────────────────────
# RECOMMENDATION CARD
# ─────────────────────────────────────────────────────────────
class RecsCard(Flowable):
    EV_HEX = {
        "Critical": "#F43F5E",
        "High":     "#F59E0B",
        "Moderate": "#00D4C8",
        "Low":      "#22C55E",
        "Routine":  "#22C55E",
    }

    def __init__(self, pw, icon, title, items, accent):
        super().__init__()
        self.pw     = pw
        self.icon   = icon
        self.title  = title
        self.items  = items
        self.accent = accent
        self._h     = None

    def wrap(self, *_):
        h = 40 + len(self.items) * 26
        self._h = h
        return self.pw, h

    def draw(self):
        c  = self.canv
        w  = self.pw
        h  = self._h
        ac = self.accent

        # Card bg
        c.setFillColor(colors.Color(ac.red, ac.green, ac.blue, alpha=0.05))
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)

        # Left stripe
        c.setFillColor(ac)
        c.roundRect(0, 0, 6, h, 4, fill=1, stroke=0)
        c.rect(3, 0, 3, h, fill=1, stroke=0)

        # Icon circle
        c.setFillColor(ac)
        c.circle(26, h - 22, 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(WHITE)
        c.drawCentredString(26, h - 26, self.icon)

        # Title
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(TEXT_HI)
        c.drawString(46, h - 26, self.title)

        # Divider
        c.setStrokeColor(colors.Color(ac.red, ac.green, ac.blue, alpha=0.20))
        c.setLineWidth(0.6)
        c.line(14, h - 36, w - 14, h - 36)

        # Items
        for idx, (badge, text, evidence) in enumerate(self.items):
            iy = h - 52 - idx * 26
            dot_hex = self.EV_HEX.get(evidence, "#00D4C8")
            dot_col = colors.HexColor(dot_hex)

            # Dot
            c.setFillColor(dot_col)
            c.circle(22, iy + 5, 4, fill=1, stroke=0)

            # Priority
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(dot_col)
            c.drawString(32, iy + 1, f"P{badge}")

            # Text
            c.setFont("Helvetica", 8.5)
            c.setFillColor(TEXT_HI)
            max_w = w - 68 - 70
            display = text
            while c.stringWidth(display, "Helvetica", 8.5) > max_w and len(display) > 20:
                display = display[:-4] + "..."
            c.drawString(52, iy + 1, display)

            # Evidence tag
            ew = c.stringWidth(evidence, "Helvetica-Bold", 6.5) + 12
            c.setFillColor(colors.Color(dot_col.red, dot_col.green, dot_col.blue, alpha=0.12))
            c.roundRect(w - ew - 8, iy - 2, ew, 14, 3, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 6.5)
            c.setFillColor(dot_col)
            c.drawCentredString(w - ew / 2 - 8, iy + 2, evidence)


# ─────────────────────────────────────────────────────────────
# FOOTER BAND
# ─────────────────────────────────────────────────────────────
class FooterBand(Flowable):
    def __init__(self, pw):
        super().__init__()
        self.pw = pw

    def wrap(self, *_): return self.pw, 44

    def draw(self):
        c = self.canv
        w = self.pw

        c.setFillColor(colors.HexColor("#F0FDFC"))
        c.roundRect(0, 0, w, 44, 8, fill=1, stroke=0)

        c.setFillColor(TEAL)
        c.roundRect(0, 42, w, 2, 1, fill=1, stroke=0)

        c.setFont("Helvetica-BoldOblique", 8)
        c.setFillColor(TEAL_DARK)
        c.drawString(14, 28, "FEMLYTIX  ·  Menstrual Screening Platform")

        c.setFont("Helvetica", 7.5)
        c.setFillColor(TEXT_LO)
        c.drawString(14, 13,
            "Screening purposes only. Not a medical diagnosis. "
            "Consult a qualified doctor for clinical evaluation.")

        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(TEAL)
        c.drawRightString(w - 14, 13, "AI-Generated Report")


# ─────────────────────────────────────────────────────────────
# RECOMMENDATION DATA
# ─────────────────────────────────────────────────────────────
def _get_recs(prediction):
    p = str(prediction).lower()

    if "pcos" in p:
        return [
            ("D", "Diet & Nutrition", TEAL, [
                ("1", "Low-GI diet: cut refined carbs and sugary drinks",           "High"),
                ("2", "Anti-inflammatory: berries, leafy greens, oily fish",        "Moderate"),
                ("3", "Inositol-rich foods: legumes, citrus, whole grains",         "Moderate"),
                ("4", "Avoid processed foods and trans-fats entirely",              "High"),
            ]),
            ("E", "Exercise", PURPLE, [
                ("1", "150+ min/week moderate cardio (walk, cycle, swim)",          "High"),
                ("2", "2x/week resistance training — improves insulin sensitivity", "High"),
                ("3", "Avoid over-training, keeps cortisol balanced",               "Moderate"),
            ]),
            ("L", "Lifestyle", colors.HexColor("#06B6D4"), [
                ("1", "Even 5% weight loss can restore ovulation in PCOS",          "High"),
                ("2", "7-9 hrs consistent sleep to regulate hormones",              "High"),
                ("3", "Daily stress relief: yoga, meditation, breathwork",          "Moderate"),
                ("4", "Track your cycle with a period app",                         "Low"),
            ]),
        ]

    if "pcod" in p:
        return [
            ("D", "Diet & Nutrition", TEAL, [
                ("1", "Balanced whole-food diet: fibre, lean protein, healthy fats","High"),
                ("2", "Reduce ultra-processed foods, trans-fats, excess sugar",    "High"),
                ("3", "Include phytoestrogen foods: flaxseeds, soy, sesame",       "Moderate"),
                ("4", "Aim for 2-2.5 litres of water daily",                       "Low"),
            ]),
            ("E", "Exercise", PURPLE, [
                ("1", "30 min moderate activity most days of the week",             "High"),
                ("2", "Yoga or pilates for hormonal and core balance",              "Moderate"),
                ("3", "Break sedentary periods — stretch every hour",               "Low"),
            ]),
            ("L", "Lifestyle", colors.HexColor("#06B6D4"), [
                ("1", "Maintain healthy BMI through consistent daily habits",       "High"),
                ("2", "Stress management: mindfulness, journalling, nature walks",  "Moderate"),
                ("3", "Avoid smoking; limit alcohol — both disrupt oestrogen",     "High"),
            ]),
        ]

    return [
        ("D", "Maintain Healthy Diet", TEAL, [
            ("1", "Balanced whole-food diet with fibre, protein, healthy fats",    "Low"),
            ("2", "Limit processed foods and excess sugar",                        "Low"),
        ]),
        ("E", "Stay Active", PURPLE, [
            ("1", "150 min/week moderate activity to maintain health",             "Low"),
            ("2", "Include strength training 2x/week",                            "Low"),
        ]),
        ("L", "Lifestyle", colors.HexColor("#06B6D4"), [
            ("1", "Track your cycle — note any changes or irregularities",         "Low"),
            ("2", "Annual gynaecological check-up is recommended",                 "Low"),
        ]),
    ]


# ─────────────────────────────────────────────────────────────
# PAGE FOOTER
# ─────────────────────────────────────────────────────────────
def _footer_cb(version, ts):
    def _draw(canvas, doc):
        canvas.saveState()
        pw = letter[0]
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.4)
        canvas.line(36, 48, pw - 36, 48)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_LO)
        canvas.drawString(36, 36, f"FEMLYTIX Menstrual Screening  ·  {version}  ·  {ts}")
        canvas.drawRightString(pw - 36, 36, f"Page {doc.page}")
        canvas.restoreState()
    return _draw


# ─────────────────────────────────────────────────────────────
# PUBLIC API  — signature unchanged
# ─────────────────────────────────────────────────────────────
def generate_prioritized_pdf(
    username, email, inputs, prediction, confidence,
    probabilities, recs,
    recs_version="v2.0", recs_timestamp=None,
):
    if recs_timestamp is None:
        recs_timestamp = datetime.now().strftime("%d %b %Y, %H:%M")

    report_id = f"HAI-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36, leftMargin=36,
        topMargin=32,   bottomMargin=62,
        title="FEMLYTIX   Menstrual Screening Report",
        author="FEMLYTIX Platform",
    )
    pw    = doc.width
    story = []

    def sp(n=10): return Spacer(1, n)

    # Augment inputs
    inp = dict(inputs)
    inp["unusual_disp"] = "Yes" if inputs.get("unusual") else "No"
    if "mean_cycle" not in inp:
        inp["mean_cycle"] = inp.get("cycle", "—")

    # ── 1. HEADER ────────────────────────────────────────────
    story.append(TopHeader(pw, username, email, report_id, recs_timestamp))
    story.append(sp(14))

    # ── 2. RESULT HERO ───────────────────────────────────────
    story.append(ResultHero(pw, prediction, confidence))
    story.append(sp(16))

    # ── 3. MEASUREMENTS ──────────────────────────────────────
    story.append(SectionPill(pw, "Clinical Measurements", TEAL))
    story.append(sp(8))
    story.append(InfoGrid(pw, inp))
    story.append(sp(16))

    # ── 4. PROBABILITY BARS ──────────────────────────────────
    story.append(SectionPill(pw, "Risk Probability Distribution", PURPLE))
    story.append(sp(8))
    story.append(ProbBars(pw, probabilities))
    story.append(sp(16))

    # ── 5. RECOMMENDATIONS ───────────────────────────────────
    story.append(SectionPill(pw, "Personalised Guidance", ROSE))
    story.append(sp(8))
    for icon, title, accent, items in _get_recs(prediction):
        story.append(RecsCard(pw, icon, title, items, accent))
        story.append(sp(8))
    story.append(sp(6))

    # ── 6. FOOTER BAND ───────────────────────────────────────
    story.append(FooterBand(pw))

    footer_fn = _footer_cb(recs_version, recs_timestamp)
    doc.build(story, onFirstPage=footer_fn, onLaterPages=footer_fn)
    buf.seek(0)
    return buf