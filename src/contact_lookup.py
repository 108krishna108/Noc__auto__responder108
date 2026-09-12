import os
import pandas as pd

# Path to Excel file
base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
excel_path = os.path.join(base_path, 'data', 'LCON.xlsx')

if not os.path.exists(excel_path):
    raise FileNotFoundError(f"Contact list not found: {excel_path}")

# Load Excel
df_contacts = pd.read_excel(excel_path)

_REQUIRED_COLUMNS = {"Hostname", "Mgr1", "Location"}
_missing = _REQUIRED_COLUMNS - set(df_contacts.columns)
if _missing:
    raise ValueError(
        f"LCON.xlsx is missing required column(s): {sorted(_missing)}. "
        f"Found columns: {list(df_contacts.columns)}"
    )


# ----------------------------------------
# Helper: extract "Name (email)" → name & email
# ----------------------------------------

def _extract_name(field: str | None) -> str | None:
    """
    Extracts only the NAME from: 'John (john@gmail.com)'
    Returns 'John'
    """
    if not field or not isinstance(field, str):
        return None

    name = field.split("(")[0].strip()
    return name if name else None


def _extract_email(field: str | None) -> str | None:
    """
    Extracts only the EMAIL from: 'John (john@gmail.com)'
    Returns 'john@gmail.com'
    """
    if not field or not isinstance(field, str):
        return None

    if "(" in field and ")" in field:
        return field.split("(")[1].split(")")[0].strip()

    return None


# ----------------------------------------
# EMAIL lookup
# ----------------------------------------

def find_mgr1_email_by_hostname(hostname: str) -> str | None:
    row = df_contacts[df_contacts['Hostname'] == hostname]
    if row.empty:
        return None
    return _extract_email(row.iloc[0]['Mgr1'])


def find_mgr2_email_by_hostname(hostname: str) -> str | None:
    row = df_contacts[df_contacts['Hostname'] == hostname]
    if row.empty or 'Mgr2' not in df_contacts.columns:
        return None
    return _extract_email(row.iloc[0]['Mgr2'])


# ----------------------------------------
# NAME lookup
# ----------------------------------------

def get_mgr1_name(hostname: str) -> str:
    row = df_contacts[df_contacts['Hostname'] == hostname]
    if row.empty:
        return "Team"
    name = _extract_name(row.iloc[0]['Mgr1'])
    return name or "Team"


def get_mgr2_name(hostname: str) -> str | None:
    row = df_contacts[df_contacts['Hostname'] == hostname]
    if row.empty or 'Mgr2' not in df_contacts.columns:
        return None
    return _extract_name(row.iloc[0]['Mgr2'])


# ----------------------------------------
# LOCATION lookup
# ----------------------------------------

def get_location(hostname: str) -> str:
    row = df_contacts[df_contacts['Hostname'] == hostname]
    if row.empty:
        return "Site"
    location = row.iloc[0]['Location']
    if not isinstance(location, str) or not location.strip():
        return "Site"
    return location.strip()
