# NOC AI Incident Response Automation

An AI-assisted Network Operations Center (NOC) automation tool that monitors an inbox for
network-device "down" alerts, identifies the affected site, enriches the incident with
operational contact data and live weather, drafts a professional incident-response email
(with Gemini rewriting the tone, and a guaranteed template fallback), and automatically sends
it to the responsible site manager(s) — with every run recorded to an audit log.

## Why this exists

NOCs receive a steady stream of automated "device unreachable" alerts from monitoring systems.
Handling one manually means: read the alert, work out which device/site it's about, look up
who's responsible for that site, check whether something like weather could explain the outage,
write a clear notification, and send it to the right person — every time, including at 3 a.m.
That's repetitive, slow, and an easy place to make mistakes (wrong contact, inconsistent tone,
a step skipped under time pressure).

This project automates that response end-to-end so the responsible site manager is notified
within minutes, with consistent and professional wording, without a human in the loop for the
common case.

## Important scope — what this is *not*

To be upfront: this is an **incident-notification assistant**, not an autonomous network-repair
system. It does **not** do this:

```
Device down → SSH into router → run commands → restart interface → verify → auto-repair
```

It does this instead:

```
Device down → understand the alert → gather site/weather context → draft guidance → notify the manager
```

A fair one-line description: *an AI-assisted NOC incident-response automation that monitors
alert emails, enriches incidents with site and weather data, uses Gemini to phrase the
notification, and automatically emails troubleshooting guidance to site managers.*

## Objectives

- Automate NOC alert intake and triage.
- Reduce repetitive manual incident-handling work.
- Automatically identify the affected device and site from the alert.
- Resolve the affected site's responsible manager(s).
- Enrich the incident with external context (weather).
- Use AI to phrase a clear, professional, context-aware notification.
- Automatically deliver that notification to the right people.
- Keep an audit trail of every run.
- Serve as a foundation for a more capable NOC automation platform over time.

## High-level flow

```
NOC mailbox
     │
     ▼
Email Monitoring  (IMAP, unread messages)
     │
     ▼
Extract Hostname  (from the alert subject)
     │
     ▼
Site / Manager Lookup  (spreadsheet: hostname → location → manager contacts)
     │
     ▼
Weather Enrichment  (site location → current conditions)
     │
     ▼
Template + AI Rewrite  (fixed template, Gemini rewrites tone; template used as-is on any failure)
     │
     ▼
Automated Email  (SMTP)
     │
     ▼
Site Manager(s)
     │
     ▼
Audit Log
```

## Architecture

```
NOC MAILBOX
     │
     ▼
EMAIL MONITOR            (src/email_monitor.py)
 - connect via IMAP
 - fetch unread messages
 - extract subject/body
 - extract hostname
     │
     ▼
CONTACT LOOKUP            (src/contact_lookup.py)
 - Hostname → Location → Manager(s)
     │
     ▼
WEATHER ENRICHMENT         (src/weather_checker.py)
 - Location → Weather API → current conditions
     │
     ▼
AGENTIC AI STEP            (src/agentic_agent.py)
 - build deterministic incident-notification template
 - Gemini rewrites it for tone/clarity (skipped on any error → template used as-is)
     │
     ▼
MAIL SENDER                (src/mail_sender.py)
 - build final email
 - send via SMTP to manager(s)
     │
     ▼
AUDIT LOG                  (logs/)
 - run status, processed alerts, errors
```

## Components

| File | Responsibility |
|---|---|
| [`src/main.py`](src/main.py) | Orchestration entry point (what the scheduler calls). Fetches unread mail, processes each one with its own error isolation so one bad email can't stop the run, and writes a per-run summary to `logs/task_log.txt`. Also has a `test` mode that runs one dummy alert through the full pipeline without touching the real inbox. |
| [`src/email_monitor.py`](src/email_monitor.py) | Connects to Gmail over IMAP, searches for unread messages, decodes MIME subject/body, and extracts the hostname as the first word of the subject (e.g. `"USRIRT0001 network device down"` → `USRIRT0001`). Returns an empty list on any IMAP/auth error rather than crashing. |
| [`src/contact_lookup.py`](src/contact_lookup.py) | Loads the site contact spreadsheet once at import time and exposes hostname-based lookups: manager name(s), manager email(s) (parsed from a `"Name (email)"` cell format), and site location. Validates required columns exist at startup, so a broken spreadsheet fails immediately and loudly instead of crashing mid-run. |
| [`src/weather_checker.py`](src/weather_checker.py) | Resolves the site's location name to an AccuWeather location key, then fetches current conditions and returns a one-line human-readable summary — or an explanatory "unavailable" message if the API/key/lookup fails at any step. |
| [`src/agentic_agent.py`](src/agentic_agent.py) | The orchestrator for a single incident. Does the lookups, builds a fixed, deterministic incident-notification email (greeting, outage statement, weather line, standard troubleshooting steps), then asks Gemini to rewrite that text in a more professional tone. If Gemini is unconfigured, errors, or returns nothing usable, the deterministic template is sent as-is — the alert is never lost because of an AI hiccup. |
| [`src/mail_sender.py`](src/mail_sender.py) | Sends the final email over SMTP, supporting multiple `to` recipients (primary + backup manager) and optional `cc`. |
| [`src/utils.py`](src/utils.py) | Small helper: picks "Good Morning" / "Good Afternoon" / "Good Evening" based on the current hour, for the email greeting. |
| `config/.env` | All credentials and API keys (Gmail app password, SMTP creds, weather key, Gemini key). Not committed — see [Security](#security). |
| `data/LCON.xlsx` | The site contact list — the project's "operational database." Hand-maintained by the NOC team. Contains real contact emails, so it's gitignored; see `data/LCON.sample.xlsx` for the expected format. |
| `logs/` | `task_log.txt` (per-run summary from `main.py`), `send_debug.txt` (detailed per-incident trace from the agent), `send_errors.txt` (SMTP send failures). |

## Data model

`data/LCON.xlsx` currently has these columns:

| Column | Used by the code today? | Notes |
|---|---|---|
| `Hostname` | Yes | Primary lookup key, matched against the alert subject. |
| `Mgr1` | Yes | Primary manager, formatted as `Name (email@example.com)`. |
| `Mgr2` | Yes (optional) | Backup manager, same format; safely skipped if the column or value is absent. |
| `Location` | Yes | Used for the weather lookup and in the email body. |
| `IP Address` | Not yet | Present in the sheet but not currently surfaced in the email or passed to Gemini — a natural next enrichment (see [Future Improvements](#future-improvements)). |
| `Site ID` | Not yet | Same as above — captured in the data, not yet used downstream. |

## End-to-end workflow

1. Scheduler (Task Scheduler / cron) runs `src/main.py`.
2. `email_monitor.fetch_unread_emails()` logs into IMAP and pulls all unread messages.
3. For each message, the hostname is parsed from the subject.
4. `contact_lookup` resolves that hostname to its manager(s) and location.
   - No manager found → the incident is skipped (logged, no email sent, no guesswork).
5. `weather_checker.get_weather_summary(location)` fetches current conditions for the site.
   - Weather API unavailable → processing continues with an "unavailable" placeholder instead of failing the whole incident.
6. `agentic_agent` builds the deterministic notification template, then asks Gemini to rewrite it for tone.
   - Gemini unavailable/errors/empty response → the deterministic template is sent unchanged.
7. `mail_sender.send_mail()` sends the final email to the manager(s) via SMTP.
   - SMTP failure → logged to `logs/send_errors.txt`; the run continues with the next incident.
8. `main.py` logs how many incidents were processed to `logs/task_log.txt`.

## Why AI is used (and where it currently stops)

A purely deterministic automation could just send a static message like *"Device down. Please
check it."* — no AI required. Today, Gemini's actual job is narrower than a full diagnostic
reasoning engine: it takes the already-complete, deterministic incident template (location,
weather, standard troubleshooting steps) and **rewrites it in a more professional, natural tone**,
with the fixed template as a guaranteed fallback if that call fails.

The natural next step — and the direction this project is heading — is to also hand Gemini richer
structured context per incident (IP address, site ID, device type, past incident history) so it
can move from *rephrasing* a fixed message toward genuinely *reasoning* about likely causes and
tailoring the troubleshooting steps to the specific device. That distinction matters: today's AI
step improves clarity and consistency, not causal analysis.

## Technology stack

- **Language:** Python
- **AI:** Google Gemini (`google-generativeai`)
- **Email:** IMAP (incoming), SMTP (outgoing) — both via Python's standard library
- **External API:** AccuWeather
- **Operational data:** Microsoft Excel (`.xlsx`, via `pandas` + `openpyxl`)
- **Configuration:** `.env` (via `python-dotenv`)
- **Logging:** plain text audit logs under `logs/`

## Project structure

```
noc_auto
├── src
│   ├── main.py             # entry point / scheduler target
│   ├── email_monitor.py    # IMAP: fetch unread alert emails
│   ├── contact_lookup.py   # Excel: hostname -> manager contacts / location
│   ├── agentic_agent.py    # decide reply content (Gemini + fallback template) and send it
│   ├── mail_sender.py      # SMTP: send the outage email
│   ├── weather_checker.py  # AccuWeather lookup for the site's location
│   └── utils.py            # small helpers (e.g. time-of-day greeting)
├── config
│   └── .env                # credentials + API keys (not committed)
├── data
│   ├── LCON.xlsx            # real site contact list (gitignored — contains real emails)
│   └── LCON.sample.xlsx     # sanitized example with the same columns, for reference
├── logs
│   ├── task_log.txt        # per-run summary log (from main.py)
│   ├── send_debug.txt      # detailed pipeline trace (from agentic_agent.py)
│   └── send_errors.txt     # SMTP send failures (from mail_sender.py)
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # On Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables** — create `config/.env`:
   ```
   # Gmail account used to both read alerts and send replies
   EMAIL_USER=your_email@gmail.com
   EMAIL_APP_PASSWORD=your_gmail_app_password

   # SMTP (usually the same Gmail account)
   SMTP_USER=your_email@gmail.com
   SMTP_PASS=your_gmail_app_password
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=465

   # AccuWeather API key (for the weather line in the email)
   ACCU_API_KEY=your_accuweather_api_key

   # Gemini API key (script falls back to a fixed template if this is
   # missing or the call fails)
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL_NAME=gemini-2.0-flash
   ```
   Gmail requires an **App Password** (not your normal login password) for IMAP/SMTP —
   generate one from your Google Account's Security settings (requires 2-Step Verification).

4. **Prepare the operational data:** place your own `LCON.xlsx` in `data/` with at least
   `Hostname`, `Mgr1`, `Mgr2` (optional), and `Location` columns. Manager cells are formatted as
   `Name (email@example.com)`. This file is gitignored since it holds real contact emails —
   see `data/LCON.sample.xlsx` for the expected structure with dummy data.

### Configuration reference

| Variable | Required | Purpose |
|---|---|---|
| `EMAIL_USER` / `EMAIL_APP_PASSWORD` | Yes | IMAP login used to read unread alerts. |
| `SMTP_USER` / `SMTP_PASS` | Yes | SMTP login used to send notifications. |
| `SMTP_HOST` / `SMTP_PORT` | No (defaults to Gmail) | Override if not using Gmail. |
| `ACCU_API_KEY` | No | Weather enrichment; without it the email just says weather is unavailable. |
| `GEMINI_API_KEY` | No | AI tone rewrite; without it the fixed template is sent as-is. |
| `GEMINI_MODEL_NAME` | No (defaults to `gemini-2.0-flash`) | Which Gemini model to call. |

## Usage

- **Production run** (fetches real unread mail from IMAP):
  ```bash
  python src/main.py
  ```
- **Test run** (skips IMAP, runs the pipeline against one dummy alert):
  ```bash
  python src/main.py test
  ```

For unattended operation, point Windows Task Scheduler (or cron) at `python src/main.py` on
whatever interval you want the inbox checked.

## Logging / audit trail

Every run appends to `logs/task_log.txt`: start/end timestamps, how many unread emails were
fetched, and per-incident success/failure. `logs/send_debug.txt` carries a more detailed trace
from the agent (lookup results, which path — Gemini vs. fallback — was used), and
`logs/send_errors.txt` captures SMTP send failures specifically. Together they answer: what
happened, when, was the incident processed, did the AI call succeed, was the notification sent,
and did an external API fail.

## Error handling (as implemented today)

| Failure | Behavior |
|---|---|
| IMAP login/fetch fails | Returns no emails for this run; no crash. Indistinguishable in the log from "genuinely zero unread mail" — see [Limitations](#current-limitations). |
| Hostname not found in the contact sheet | Incident is skipped — no email sent, no guessing. |
| Weather API fails | Processing continues; email includes an "unavailable" placeholder instead of a weather line. |
| Gemini call fails/empty/unconfigured | The deterministic fallback template is sent instead — the notification still goes out. |
| SMTP send fails | Logged to `logs/send_errors.txt`; the run continues to the next incident. |

Note: none of the above currently retry — each stage fails safe (skip/fallback/log) rather than
retrying. Automatic retries are listed under [Future Improvements](#future-improvements).

## Testing

There's a built-in manual test path (`python src/main.py test`) that runs one dummy alert through
the entire pipeline — lookup, weather, Gemini, and a real SMTP send — without touching the real
mailbox, useful for verifying the whole chain end to end. There is currently no automated test
suite. Suggested manual scenarios to exercise:

1. **Normal alert** — known hostname, weather available, Gemini available → email sent.
2. **Unknown device** — hostname not in the spreadsheet → incident skipped, no email sent.
3. **Weather outage** — invalid/missing weather key → email sent with a placeholder weather line.
4. **AI outage** — invalid/missing Gemini key → fixed-template email still sent.
5. **SMTP outage** — bad SMTP credentials → failure logged to `send_errors.txt`, no crash.

## Current limitations

- Hostname extraction assumes "first word of the subject" — a change in the monitoring system's
  alert format silently breaks the match (incident just gets skipped).
- IMAP errors (bad credentials, network issues) and "genuinely zero unread mail" both log as
  `"Fetched 0 unread mail(s)"` — there's no separate signal if the mailbox login itself starts failing.
- The contact list is a manually maintained spreadsheet; it's only as accurate as its last edit.
- Weather is resolved by location *name* via AccuWeather's city search, so ambiguous or
  misspelled locations can resolve to the wrong city.
- `IP Address` and `Site ID` are present in the data but not yet used anywhere downstream.
- No retries on transient IMAP/Gemini/SMTP failures — each just fails safe and logs.
- No incident severity/classification, no escalation path, and no persistent database — this is
  a single-pass, stateless script by design (see [Future Improvements](#future-improvements)).
- No automated test suite, only the manual dummy-alert test mode.

## Benefits

- Reduces manual NOC workload for a routine, repetitive task.
- Faster incident acknowledgement — no waiting on a human to notice the alert.
- Consistent, professional incident communication regardless of time of day.
- Automated, spreadsheet-driven manager identification (no manual contact digging).
- Weather-aware context included automatically.
- Centralized audit logging of every run.
- A clean foundation to build more advanced NOC automation on top of.

## Future improvements

Roadmap ideas, not yet implemented:

1. **Replace Excel with a real database** (PostgreSQL/MySQL/SQLite) — `devices`, `sites`,
   `managers`, `incidents`, `incident_history` tables instead of a hand-edited spreadsheet.
2. **Incident classification** — severity levels (CRITICAL/HIGH/MEDIUM/LOW) based on device
   criticality, driving different notification urgency.
3. **Automatic escalation** — if the primary manager doesn't acknowledge within a time window,
   escalate to a NOC lead, then network engineering.
4. **Feed Gemini richer context** — IP address, device type, vendor, and past incident history,
   so the AI moves from rephrasing a fixed message to actually reasoning about likely causes.
5. **Controlled network diagnostics** — ping / DNS / port / SNMP checks (and eventually
   read-only SSH diagnostics) run automatically and fed to the AI for analysis, always short of
   automatic remediation.
6. **Human-in-the-loop approval** for any action riskier than "send a notification."
7. **A web dashboard** (FastAPI/Flask + a frontend, or Streamlit) showing active incidents,
   severities, and per-device status instead of a plain text log.
8. **Retry logic** for transient IMAP/Gemini/SMTP failures instead of failing safe on first error.
9. **Multi-agent architecture** — a longer-term idea: an orchestrator agent routing to
   specialized diagnostic/knowledge/escalation agents, with a human-approval gate before any
   automated action, rather than one linear script.

## Security

- All credentials live in `config/.env`, which is excluded via `.gitignore` — **never commit it.**
- If a key or app password is ever exposed (e.g. pushed by accident), revoke and rotate it
  immediately at the provider (Google, Gemini, AccuWeather) rather than just removing it from
  the repo.
- `logs/` is also gitignored — the debug/error logs can contain hostnames, locations, and manager
  emails, which don't belong in a public repository history.

## Elevator pitch

Built a Python-based NOC automation system that monitors network alert emails, maps affected
devices to site and manager contacts, enriches incidents with weather data, uses Gemini to draft
a clear and professional notification (with a deterministic fallback so a notification is never
lost to an AI failure), and automatically distributes it via email with full audit logging.

## Conclusion

This project shows how a fairly ordinary IT/NOC automation — mailbox polling, spreadsheet lookup,
a weather API call, an SMTP send — becomes noticeably more useful once a language model is given
one well-scoped job inside it: turning a rigid template into a clear, professional message,
without ever being allowed to block the actual delivery of the alert. It's intentionally a small,
linear, dependency-light script today, with a clear path toward richer context, a real database,
classification, escalation, and eventually a proper dashboard, if it needs to grow into that.

## License

MIT.
