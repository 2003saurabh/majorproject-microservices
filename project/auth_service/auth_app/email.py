import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from auth_app.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)


def _html_otp(otp: str, purpose: str, app_name: str) -> str:
    titles = {
        "verify": "Verify your email address",
        "reset":  "Reset your password",
        "login":  "Your login code",
    }
    subtitles = {
        "verify": "Enter this code to complete your registration.",
        "reset":  "Enter this code to reset your password. If you didn't request this, ignore this email.",
        "login":  "Enter this code to sign in to your account.",
    }
    title    = titles.get(purpose, "Your OTP code")
    subtitle = subtitles.get(purpose, "Use this code to continue.")

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    body {{ margin:0; padding:0; background:#0a0a0f; font-family:'Segoe UI',Arial,sans-serif; }}
    .wrap {{ max-width:520px; margin:40px auto; background:#111118; border:1px solid #23232f;
             border-radius:12px; overflow:hidden; }}
    .header {{ background:#16161f; padding:28px 32px; border-bottom:1px solid #23232f; }}
    .logo {{ font-size:20px; font-weight:800; color:#00e5a0; letter-spacing:-0.5px; }}
    .body {{ padding:32px; }}
    h2 {{ color:#e8e8f0; font-size:22px; margin:0 0 8px; }}
    p {{ color:#6b6b80; font-size:14px; line-height:1.6; margin:0 0 24px; }}
    .otp-box {{ background:#0a0a0f; border:1px solid #23232f; border-radius:10px;
                padding:20px; text-align:center; margin:0 0 24px; }}
    .otp {{ font-size:38px; font-weight:700; letter-spacing:12px; color:#00e5a0;
            font-family:'Courier New',monospace; }}
    .expiry {{ color:#6b6b80; font-size:12px; margin-top:8px; }}
    .footer {{ padding:20px 32px; border-top:1px solid #23232f;
               color:#6b6b80; font-size:12px; text-align:center; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header"><div class="logo">⬡ {app_name}</div></div>
    <div class="body">
      <h2>{title}</h2>
      <p>{subtitle}</p>
      <div class="otp-box">
        <div class="otp">{otp}</div>
        <div class="expiry">Expires in {settings.OTP_EXPIRE_MINUTES} minutes</div>
      </div>
      <p style="font-size:12px;">Do not share this code with anyone.</p>
    </div>
    <div class="footer">&copy; {app_name} &mdash; Automated message, do not reply.</div>
  </div>
</body>
</html>
"""


async def send_otp_email(to_email: str, otp: str, purpose: str) -> bool:
    """
    Send OTP email via Gmail SMTP (TLS on port 587).
    Returns True on success, False on failure (so the API can still respond).
    """
    if not settings.EMAIL_ENABLED:
        log.info("[email disabled] OTP %s → %s  code=%s", purpose, to_email, otp)
        return True

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        log.warning("SMTP_USER / SMTP_PASSWORD not configured — skipping email")
        return False

    subjects = {
        "verify": f"[{settings.APP_NAME}] Verify your email — {otp}",
        "reset":  f"[{settings.APP_NAME}] Password reset code — {otp}",
        "login":  f"[{settings.APP_NAME}] Your login code — {otp}",
    }
    subject = subjects.get(purpose, f"[{settings.APP_NAME}] Your OTP — {otp}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.sender_email
    msg["To"]      = to_email
    msg.attach(MIMEText(f"Your {purpose} OTP is: {otp}  (expires in {settings.OTP_EXPIRE_MINUTES} min)", "plain"))
    msg.attach(MIMEText(_html_otp(otp, purpose, settings.APP_NAME), "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        log.info("OTP email sent → %s  purpose=%s", to_email, purpose)
        return True
    except Exception as exc:
        log.error("Failed to send OTP email to %s: %s", to_email, exc)
        return False
