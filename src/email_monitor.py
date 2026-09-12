# email_monitor.py

import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv
from email.message import Message

# Load environment from config/.env
ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    ".env",
)
load_dotenv(ENV_PATH)


def parse_hostname_from_subject(subject: str | None) -> str | None:
    """
    Extract hostname from the subject.
    Current logic: take the first word.
    Example:
        'USRIRT0001 network device down' -> 'USRIRT0001'
    """
    return subject.split()[0] if subject else None


def _decode_mime_header(value: str | None) -> str:
    """
    Safely decode MIME-encoded headers (e.g. subject).
    Returns a clean UTF-8 string.
    """
    if not value:
        return ""

    parts = decode_header(value)
    decoded_chunks = []

    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            enc = enc or "utf-8"
            try:
                decoded_chunks.append(chunk.decode(enc, errors="ignore"))
            except Exception:
                decoded_chunks.append(chunk.decode("utf-8", errors="ignore"))
        else:
            decoded_chunks.append(chunk)

    return "".join(decoded_chunks)


def _extract_body_from_message(msg: Message) -> str:
    """
    Extract a plain-text body from an email.message.Message.
    Prefers 'text/plain' and ignores attachments.
    """
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="ignore")
                except Exception:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
        return ""
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset, errors="ignore")
        except Exception:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")


def fetch_unread_emails() -> list[dict]:
    """
    Fetch unread emails from Gmail via IMAP.

    Returns a list of dicts:
    [
        {
            "id": b"123",
            "subject": "...",
            "from": "...",
            "body": "...",
            "hostname": "USRIRT0001"
        },
        ...
    ]

    On any fatal error (invalid credentials, connection issues, etc.),
    returns an empty list.
    """
    # Prefer dedicated IMAP creds, fallback to SMTP creds
    user = os.getenv("EMAIL_USER") or os.getenv("SMTP_USER")
    password = os.getenv("EMAIL_APP_PASSWORD") or os.getenv("SMTP_PASS")

    if not user or not password:
        # No prints in production; just fail silently and let caller decide.
        return []

    imap = None
    mails: list[dict] = []

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(user, password)

        imap.select("INBOX")
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return []

        msg_ids = data[0].split()
        for m_id in msg_ids:
            status, msg_data = imap.fetch(m_id, "(RFC822)")
            if status != "OK":
                continue

            raw_msg = msg_data[0][1]
            msg = email.message_from_bytes(raw_msg)

            raw_subject = msg.get("Subject")
            subject = _decode_mime_header(raw_subject)
            from_ = _decode_mime_header(msg.get("From"))

            body = _extract_body_from_message(msg)
            hostname = parse_hostname_from_subject(subject)

            mails.append(
                {
                    "id": m_id,
                    "subject": subject,
                    "from": from_,
                    "body": body,
                    "hostname": hostname,
                }
            )

        return mails

    except imaplib.IMAP4.error:
        # Authentication / IMAP error — treat as no mails
        return []
    except Exception:
        # Any unexpected error — treat as no mails
        return []
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass
