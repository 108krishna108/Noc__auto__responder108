# mail_sender.py

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from dotenv import load_dotenv
import datetime
from typing import Union, Iterable

# Load .env
ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    ".env",
)
load_dotenv(ENV_PATH)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")           # e.g. veersingh1086870@gmail.com
SMTP_PASS = os.getenv("SMTP_PASS")           # 16-character app password

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
ERROR_LOG = os.path.join(LOG_DIR, "send_errors.txt")


def _normalize_recipients(value: Union[str, Iterable[str], None]) -> list[str]:
    """
    Helper: string ya iterable ko clean list me convert karega.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    # strip + empty remove
    result = []
    for v in value:
        v = (v or "").strip()
        if v:
            result.append(v)
    return result


def send_mail(
    to: Union[str, Iterable[str]],
    subject: str,
    body: str,
    cc: Union[str, Iterable[str], None] = None,
) -> None:
    """
    Ab ye function multiple recipients support karta hai.

    - to: ek string ya list/tuple of emails
    - cc: optional string ya list/tuple of emails
    """
    to_list = _normalize_recipients(to)
    cc_list = _normalize_recipients(cc)
    all_recipients = list(dict.fromkeys(to_list + cc_list))  # unique order

    if not all_recipients:
        # koi recipient hi nahi, to kuch mat send karo
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, all_recipients, msg.as_string())
    except Exception as e:
        ts = datetime.datetime.now()
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"{ts} - Failed sending to {all_recipients}: {e}\n")
        except Exception:
            # logging fail ho jaye to bhi function silently exit kare
            pass


if __name__ == "__main__":
    # Optional: quick self-test
    if SMTP_USER:
        send_mail(
            to=SMTP_USER,
            subject="Python SMTP multi-recipient test",
            body="This is a test mail from mail_sender.py (multi-recipient version)",
        )
        print("Test mail sent (if no error in send_errors.txt).")
    else:
        print("SMTP_USER not set in .env")
