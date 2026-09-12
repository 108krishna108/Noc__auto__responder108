# agentic_agent.py

import os
import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from mail_sender import send_mail
from contact_lookup import (
    find_mgr1_email_by_hostname,
    find_mgr2_email_by_hostname,
    get_mgr1_name,
    get_mgr2_name,
    get_location,
)
from utils import current_greeting
from weather_checker import get_weather_summary

# ---------------------------------------------------
# ENV + Gemini configuration
# ---------------------------------------------------

ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    ".env",
)
load_dotenv(ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
DEBUG_LOG = os.path.join(LOG_DIR, "send_debug.txt")


def dlog(msg: str) -> None:
    ts = datetime.datetime.now()
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} - {msg}\n")
    except:
        pass


# ---------------------------------------------------
# Build template-based NOC email body
# ---------------------------------------------------

def build_noc_email_body(
    greeting: str,
    mgr1_name: str,
    mgr2_name: str | None,
    location: str,
    weather_summary: str,
):
    """Creates the clean NOC outage email in the exact structure you requested."""

    # Greeting names
    if mgr2_name:
        display_name = f"{mgr1_name} / {mgr2_name}"
    else:
        display_name = mgr1_name

    lines = [
        f"{greeting} {display_name},",
        "",
        f"This alert is to inform you of a potential network outage at {location}.",
        "",
        weather_summary,
        "",
        (
            f"The {location} site/device is currently unreachable from NOC monitoring "
            "and may be experiencing a service disruption. We recommend the following "
            "basic troubleshooting steps be performed by a local onsite technician:"
        ),
        "",
        "Potential Troubleshooting Steps:",
        "",
        "1.  Physical Inspection: Visually inspect the affected device and surrounding "
        "equipment for any obvious issues, such as disconnected cables, tripped power "
        "switches, or damaged components.",
        "",
        "2.  Power Cycle (Reboot):",
        "    • Carefully disconnect the power cable from the device.",
        "    • Wait approximately 60 seconds.",
        "    • Reconnect the power cable.",
        "    • Allow the device sufficient time to fully boot up.",
        "",
        "3.  Connectivity Check: Once the device has rebooted, attempt to connect to the "
        "network and verify its internet connectivity. Check link lights and console "
        "access, if available.",
        "",
        "If the issue persists after completing these steps, please escalate to the next "
        "level of support with a detailed description of the symptoms and the "
        "troubleshooting steps already taken.",
        "",
        "NOC Automation Team",
    ]

    return "\n".join(lines)


# ---------------------------------------------------
# Gemini with safe fallback
# ---------------------------------------------------

def _safe_gemini_generate(prompt: str, fallback_body: str) -> str:
    """Try Gemini → If ANY error happens, return fallback_body."""

    if not GEMINI_API_KEY:
        dlog("Gemini API key missing → using fallback template.")
        return fallback_body

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        dlog(f"Calling Gemini model: {GEMINI_MODEL_NAME}")
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)

        # Parse fallback candidate format
        if (not text) and getattr(response, "candidates", None):
            try:
                parts = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text"):
                        parts.append(part.text)
                text = "\n".join(parts)
            except:
                text = None

        if not text:
            dlog("Gemini returned empty response → fallback.")
            return fallback_body

        return text

    except Exception as e:
        dlog(f"Gemini error: {e} → fallback triggered.")
        return fallback_body


# ---------------------------------------------------
# Main agent: lookup → template → try Gemini → send mail
# ---------------------------------------------------

def agentic_decide_and_reply(mail: dict) -> None:
    subject = mail.get("subject", "")
    hostname = mail.get("hostname", "")

    dlog(f"Processing mail for host={hostname}, subject={subject}")

    # Lookup info from Excel
    mgr1_email = find_mgr1_email_by_hostname(hostname)
    mgr2_email = find_mgr2_email_by_hostname(hostname)
    mgr1_name = get_mgr1_name(hostname)
    mgr2_name = get_mgr2_name(hostname)
    location = get_location(hostname)
    greeting = current_greeting()

    dlog(
        f"Lookup → Mgr1={mgr1_email}, Mgr2={mgr2_email}, "
        f"Names=({mgr1_name}, {mgr2_name}), Location={location}"
    )

    recipients = []
    if mgr1_email:
        recipients.append(mgr1_email)
    if mgr2_email:
        recipients.append(mgr2_email)

    if not recipients:
        dlog("No manager emails → skipping.")
        return

    # Get weather
    try:
        weather_summary = get_weather_summary(location)
    except Exception as e:
        weather_summary = "Weather information unavailable."
        dlog(f"Weather API error: {e}")

    # Build template
    fallback_body = build_noc_email_body(
        greeting=greeting,
        mgr1_name=mgr1_name,
        mgr2_name=mgr2_name,
        location=location,
        weather_summary=weather_summary,
    )

    # Try Gemini rewrite → fallback safe
    prompt = (
        "Rewrite the following NOC outage email in a professional tone. "
        "Keep structure same (greeting, location, weather, outage statement, steps, closing). "
        "Do NOT change the technical meaning.\n\n"
        f"{fallback_body}"
    )

    final_body = _safe_gemini_generate(prompt, fallback_body)

    # Subject line
    if subject:
        final_subject = f"Re: {subject}"
    else:
        final_subject = "NOC Alert: Device Down"

    # Send mail
    try:
        send_mail(
            to=recipients,
            subject=final_subject,
            body=final_body,
        )
        dlog(f"Mail sent to: {', '.join(recipients)}")

    except Exception as e:
        dlog(f"send_mail ERROR: {e}")


if __name__ == "__main__":
    dummy = {
        "subject": "USRIRT0001 network device down",
        "hostname": "USRIRT0001",
    }
    agentic_decide_and_reply(dummy)
