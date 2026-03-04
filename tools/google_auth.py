"""
Shared Google OAuth2 credentials for Calendar, Gmail, Drive, GA4, Sheets, Slides.
Run this script once to authorize and create/update token.json.
All other Google tools use get_credentials() from this module.
"""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Paths relative to project root (parent of tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

# Scopes for all Google tools we use
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]


def get_credentials():
    """
    Load credentials from token.json, refreshing if needed.
    Returns None if token.json is missing. Use run_oauth_flow() to create it.
    """
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
    return creds


def run_oauth_flow():
    """
    Run the OAuth2 flow and save credentials to token.json.
    Call this when token.json is missing or you need to re-authorize (e.g. new scopes).
    """
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_FILE}. Download OAuth 2.0 credentials from "
            "Google Cloud Console (Desktop app) and save as credentials.json. "
            "See workflows/google_setup.md."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print(f"Credentials saved to {TOKEN_FILE}")
    return creds


def main():
    """Authorize and save token.json for use by other tools."""
    creds = get_credentials()
    if creds is None or not creds.valid:
        run_oauth_flow()
    else:
        print("Existing credentials are valid. No action needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
