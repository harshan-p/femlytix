# auth_email.py  —  FEMLYTIX Elite Email Authentication
# =========================================================
# Handles: OTP generation · Email sending · Token lifecycle
# Supports: Gmail, Outlook, SendGrid SMTP relay, Mailgun, any SMTP
# Config:   .streamlit/secrets.toml  OR  environment variables
# =========================================================

import os
import random
import secrets
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ─────────────────────────────────────────────────────────────
# CONFIG  —  reads from Streamlit secrets with env-var fallback
# ─────────────────────────────────────────────────────────────
def get_smtp_config() -> dict:
    """
    Priority: st.secrets["smtp"] → env vars → empty (will fail gracefully).

    secrets.toml example:
        [smtp]
        host       = "smtp.gmail.com"
        port       = 587
        username   = "your@gmail.com"
        password   = "your_app_password"   # Gmail: 16-char App Password
        from_email = "your@gmail.com"      # optional, defaults to username
        from_name  = "FEMLYTIX"            # optional
    """
    try:
        import streamlit as st  # lazy import so module works without streamlit
        s = st.secrets["smtp"]
        return {
            "host":       s["host"],
            "port":       int(s["port"]),
            "username":   s["username"],
            "password":   s["password"],
            "from_email": s.get("from_email", s["username"]),
            "from_name":  s.get("from_name", "FEMLYTIX"),
        }
    except Exception:
        pass

    return {
        "host":       os.getenv("SMTP_HOST",      "smtp.gmail.com"),
        "port":       int(os.getenv("SMTP_PORT",  "587")),
        "username":   os.getenv("SMTP_USERNAME",  ""),
        "password":   os.getenv("SMTP_PASSWORD",  ""),
        "from_email": os.getenv("SMTP_FROM",      os.getenv("SMTP_USERNAME", "")),
        "from_name":  os.getenv("SMTP_FROM_NAME", "FEMLYTIX"),
    }


# ─────────────────────────────────────────────────────────────
# TOKEN / OTP UTILITIES
# ─────────────────────────────────────────────────────────────
def generate_otp(length: int = 6) -> str:
    """Cryptographically random numeric OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(nbytes: int = 32) -> str:
    """URL-safe random token for future link-based flows."""
    return secrets.token_urlsafe(nbytes)


def otp_expiry(minutes: int = 15) -> str:
    """Return UTC expiry ISO-string."""
    return (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()


def is_expired(expiry_iso: str) -> bool:
    """Return True if the ISO timestamp is in the past (or invalid)."""
    try:
        return datetime.utcnow() > datetime.fromisoformat(expiry_iso)
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────
# CORE SMTP SENDER
# ─────────────────────────────────────────────────────────────
def send_email(to_email: str, subject: str,
               html_body: str, text_body: str | None = None) -> tuple[bool, str | None]:
    """
    Send an HTML email via STARTTLS SMTP.
    Returns (success: bool, error_message: str | None).
    """
    cfg = get_smtp_config()

    if not cfg["username"] or not cfg["password"]:
        return False, (
            "SMTP is not configured. Add [smtp] block to .streamlit/secrets.toml "
            "or set SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD env vars."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"]      = to_email
    msg["X-Mailer"] = "FEMLYTIX-Auth/1.0"

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=12) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(cfg["username"], cfg["password"])
            srv.sendmail(cfg["from_email"], to_email, msg.as_string())
        return True, None

    except smtplib.SMTPAuthenticationError:
        return False, (
            "SMTP authentication failed. "
            "For Gmail use a 16-char App Password (not your account password). "
            "Enable 2FA first, then visit myaccount.google.com → Security → App Passwords."
        )
    except smtplib.SMTPRecipientsRefused:
        return False, f"Email address '{to_email}' was rejected by the mail server."
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except TimeoutError:
        return False, "Connection to mail server timed out. Check SMTP host/port."
    except Exception as exc:
        return False, f"Unexpected email error: {exc}"


# ─────────────────────────────────────────────────────────────
# EMAIL TEMPLATES  —  dark-themed, matching the FEMLYTIX palette
# ─────────────────────────────────────────────────────────────

def _base_layout(header_accent: str, header_label: str,
                 title: str, body_html: str, otp: str,
                 otp_accent: str, expiry_note: str = "Expires in 15 minutes") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#050c1a;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#050c1a;min-height:100vh;">
    <tr><td align="center" style="padding:40px 16px;">

      <!-- Card -->
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:linear-gradient(135deg,#081120 0%,#0d1f40 100%);
                    border:1px solid {header_accent}30;
                    border-radius:20px;overflow:hidden;
                    box-shadow:0 16px 64px rgba(0,0,0,0.6);">

        <!-- Header bar -->
        <tr>
          <td style="background:linear-gradient(135deg,#060f22,#0d1f40);
                     padding:28px 40px 22px;text-align:center;
                     border-bottom:1px solid {header_accent}18;">
            <p style="margin:0 0 4px;font-size:10px;letter-spacing:3.5px;
                      text-transform:uppercase;color:{header_accent};font-weight:700;">
              {header_label}
            </p>
            <h1 style="margin:0;font-size:26px;color:#e8f0fe;
                       font-weight:800;letter-spacing:1.5px;">
              FEMLYTIX
            </h1>
            <p style="margin:4px 0 0;font-size:10px;color:#2d3748;
                      letter-spacing:1.5px;text-transform:uppercase;">
              Menstrual Screening Platform
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px 28px;">
            {body_html}

            <!-- OTP Box -->
            <div style="background:{otp_accent}0e;
                        border:1.5px solid {otp_accent}40;
                        border-radius:16px;padding:30px 24px;
                        text-align:center;margin:24px 0 20px;">
              <p style="margin:0 0 10px;font-size:10px;letter-spacing:3px;
                        text-transform:uppercase;color:{otp_accent};font-weight:700;">
                Verification Code
              </p>
              <p style="margin:0;font-size:48px;font-weight:900;
                        letter-spacing:14px;color:#e8f0fe;
                        font-family:'Courier New',Courier,monospace;">
                {otp}
              </p>
              <p style="margin:12px 0 0;font-size:12px;color:#4a5568;">
                ⏱ <strong style="color:#f59e0b;">{expiry_note}</strong>
              </p>
            </div>

            <p style="margin:0;color:#4a5568;font-size:12px;line-height:1.6;">
              This code is single-use and cannot be reused after verification.
              If you did not request this, you can safely ignore this email — your
              account (if any) remains secure.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 40px 28px;
                     border-top:1px solid rgba(255,255,255,0.05);
                     text-align:center;">
            <p style="margin:0 0 4px;font-size:11px;color:#2d3748;">
              ⚕️ FEMLYTIX · AI Screening Platform &nbsp;·&nbsp;
              <span style="color:#1a2035;">Automated message — do not reply.</span>
            </p>
            <p style="margin:0;font-size:10px;color:#1a2035;">
              Not a diagnostic device. Always consult a healthcare professional.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def verification_email_html(name: str, otp: str) -> str:
    body = f"""
<h2 style="margin:0 0 10px;font-size:22px;color:#e8f0fe;font-weight:700;">
  Verify your email address
</h2>
<p style="margin:0 0 20px;color:#94a3b8;font-size:15px;line-height:1.65;">
  Hi <strong style="color:#e8f0fe;">{name}</strong>, thanks for joining FEMLYTIX.<br>
  Enter the 6-digit code below inside the app to activate your account.
</p>"""
    return _base_layout(
        header_accent="#00d4c8",
        header_label="⚕ Account Verification",
        title="Verify your FEMLYTIX account",
        body_html=body,
        otp=otp,
        otp_accent="#00d4c8",
    )


def password_reset_email_html(name: str, otp: str) -> str:
    body = f"""
<h2 style="margin:0 0 10px;font-size:22px;color:#e8f0fe;font-weight:700;">
  Password Reset Request
</h2>
<p style="margin:0 0 20px;color:#94a3b8;font-size:15px;line-height:1.65;">
  Hi <strong style="color:#e8f0fe;">{name}</strong>, we received a request to
  reset your FEMLYTIX password.<br>
  Enter the code below to set a new password.
</p>"""
    return _base_layout(
        header_accent="#ff6b8a",
        header_label="🔐 Security Alert",
        title="Reset your FEMLYTIX password",
        body_html=body,
        otp=otp,
        otp_accent="#ff6b8a",
    )


# ─────────────────────────────────────────────────────────────
# PUBLIC SEND HELPERS
# ─────────────────────────────────────────────────────────────

def send_verification_email(to_email: str, name: str, otp: str) -> tuple[bool, str | None]:
    subject   = "🔐 Your FEMLYTIX verification code"
    html_body = verification_email_html(name, otp)
    text_body = (
        f"Hi {name},\n\n"
        f"Your FEMLYTIX account verification code is:\n\n"
        f"  {otp}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"If you didn't create an account, please ignore this email.\n\n"
        f"— FEMLYTIX Team"
    )
    return send_email(to_email, subject, html_body, text_body)


def send_password_reset_email(to_email: str, name: str, otp: str) -> tuple[bool, str | None]:
    subject   = "🔑 FEMLYTIX password reset code"
    html_body = password_reset_email_html(name, otp)
    text_body = (
        f"Hi {name},\n\n"
        f"Your FEMLYTIX password reset code is:\n\n"
        f"  {otp}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"If you didn't request this reset, you can ignore this email — "
        f"your password will not change.\n\n"
        f"— FEMLYTIX Team"
    )
    return send_email(to_email, subject, html_body, text_body)

print(get_smtp_config())