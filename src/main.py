# main.py

import datetime
import os
import sys

from email_monitor import fetch_unread_emails
from agentic_agent import agentic_decide_and_reply

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# Central log file for NOC automation runs
# NOTE: Yehi file check karni hai: C:\Users\91870\task_log.txt
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "task_log.txt")



def log(msg: str) -> None:
    """
    Simple file logger for the main scheduler script.
    Writes timestamp + message into LOG_PATH.
    Also prints to console (helpful for debugging).
    """
    ts = datetime.datetime.now()
    line = f"{ts} - {msg}"
    # Console pe bhi dikhayenge (especially test mode me helpful)
    print("[LOG]", line)

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        # Agar logging file pe issue ho, wo bhi console me dikh jayega
        print(f"[LOG ERROR] Could not write to {LOG_PATH}: {e}")


def process_unread_emails() -> int:
    """
    Core processing function:

    1. Fetch unread emails via email_monitor.fetch_unread_emails().
    2. For each mail, call agentic_decide_and_reply() to:
       - lookup manager
       - get weather
       - call Gemini
       - send email.

    Returns:
        int: Number of emails that were processed.
    """
    unread_emails = fetch_unread_emails()
    count = len(unread_emails)

    log(f"Fetched {count} unread mail(s) from mailbox.")

    for mail in unread_emails:
        subject = mail.get("subject", "NO_SUBJECT")
        hostname = mail.get("hostname", "NO_HOST")

        log(f"Processing mail: host={hostname}, subject={subject}")

        try:
            agentic_decide_and_reply(mail)
            log(f"Successfully processed mail: host={hostname}, subject={subject}")
        except Exception as e:
            # We catch everything here so that one bad email
            # does not stop the whole run.
            log(f"ERROR while processing mail host={hostname}, subject={subject}: {e}")

    return count


def main() -> None:
    """
    Entry point for production use.
    Intended to be called by Task Scheduler or a cron job.

    - Logs start/end of the script.
    - Calls process_unread_emails() once per run.
    """
    log(f"NOC automation script started. LOG_PATH = {LOG_PATH}")
    try:
        processed = process_unread_emails()
        log(f"NOC automation script finished. Processed {processed} mail(s).")
    except Exception as e:
        log(f"FATAL ERROR in main(): {e}")


# -------------------------------------------------------------------
# Test mode (manual verification)
# -------------------------------------------------------------------

def test_with_dummy_mail() -> None:
    """
    Test helper:

    Runs the pipeline with a single dummy mail without touching IMAP.
    This is useful to verify that:

    - contact_lookup (Excel) is working,
    - Gemini integration is working,
    - SMTP mail sending works,
    - logging is working.
    """
    log("TEST MODE: Starting dummy mail test run.")

    dummy_mail = {
        "subject": "USRIRT0001 network device down",
        "body": "Test device unreachable from NOC. Please investigate.",
        "hostname": "USRIRT0001",
    }

    try:
        agentic_decide_and_reply(dummy_mail)
        log("TEST MODE: Dummy mail processed successfully.")
    except Exception as e:
        log(f"TEST MODE: ERROR while processing dummy mail: {e}")


if __name__ == "__main__":
    """
    Command-line usage:

    1) Production mode (default):
       python main.py

    2) Test mode (no IMAP, just one dummy email):
       python main.py test
    """
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        test_with_dummy_mail()
    else:
        main()
