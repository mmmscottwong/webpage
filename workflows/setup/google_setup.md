# Workflow: Connect Google APIs

## Objective
Enable the project to use Google Calendar, Gmail, Drive, GA4, Sheets, and Slides with a single OAuth flow. One token covers all requested scopes.

## Required inputs
- **Google Cloud project** with the following APIs enabled:
  - Google Calendar API
  - Gmail API
  - Google Drive API
  - Google Analytics Data API (GA4)
  - Google Analytics Admin API (required for `google_ga4.py --list-properties` to list property IDs)
  - Google Sheets API
  - Google Slides API
- **OAuth 2.0 Client ID** (Desktop app) downloaded as `credentials.json` in the project root.
- **OAuth consent screen** configured (External for testing; add your Google account as a test user).

## Tools to use
- `tools/google_auth.py` — run once to authorize and create/update `token.json` with all scopes.

## Steps

### 1. Enable APIs in Google Cloud Console
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → your project (or create one).
2. **APIs & Services** → **Library**.
3. Search and enable each API listed above.

### 2. Configure OAuth consent screen
1. **APIs & Services** → **OAuth consent screen**.
2. User type: **External** (for personal/testing).
3. Add scopes if prompted; the auth script requests them at runtime.
4. Add your Google account under **Test users** so you can sign in.

### 3. Create OAuth client credentials
1. **APIs & Services** → **Credentials** → **Create credentials** → **OAuth client ID**.
2. Application type: **Desktop app**.
3. Download JSON and save as `credentials.json` in the project root (same folder as `CLAUDE.md`).
4. Ensure `credentials.json` is in `.gitignore` (it is).

### 4. Run the auth tool (one-time per machine / when adding scopes)

**Windows Terminal (PowerShell or Command Prompt):** from the project root (`d:\Agent` or wherever the repo lives):

```powershell
cd d:\Agent
py -m pip install -r requirements.txt
py tools/google_auth.py
```

Use `py` (Python launcher) so you don’t need `python` or `pip` on PATH. If `py` isn’t found, [install Python from python.org](https://www.python.org/downloads/) and check “Add python.exe to PATH”, then try `python -m pip install -r requirements.txt` and `python tools\google_auth.py`.

- A browser opens; sign in with the Google account that should own the data.
- Grant the requested permissions.
- Credentials are saved to `token.json` and reused by all Google tools.

### 5. Use the Google tools
After `token.json` exists, from the project root run any of (PowerShell or CMD):

```powershell
py tools/google_calendar.py --calendars
py tools/google_calendar.py --upcoming
py tools/google_gmail.py --list
py tools/google_drive.py --list
py tools/google_ga4.py --list-properties
py tools/google_ga4.py --report
py tools/google_sheets.py --read --spreadsheet-id "YOUR_ID" --range "Sheet1!A1:D10"
py tools/google_slides.py --list --presentation-id "YOUR_ID"
```

They all use the shared credentials from `tools/google_auth.py`.

## Expected outputs
- `credentials.json` (you create from Console; not in git).
- `token.json` (created by `google_auth.py`; not in git).
- Ability to call Calendar, Gmail, Drive, GA4, Sheets, and Slides from the tools.

## Edge cases / notes
- **Windows**: Run all commands from the project root in Windows Terminal (PowerShell) or Command Prompt. Use `python tools\script.py` or `python tools/script.py`; both work.
- **Scope changes**: If you add a new Google product later, add its scope in `tools/google_auth.py`, then run `google_auth.py` again so the new scope is in `token.json`.
- **Token expiry**: Refresh tokens are stored; the auth module refreshes access tokens automatically. If you revoke app access in your Google account, delete `token.json` and run `google_auth.py` again.
- **403 / scope errors**: Ensure the right API is enabled in Cloud Console and the scope in `google_auth.py` matches the API (e.g. GA4 Data vs Admin). If you see "Google Analytics Admin API has not been used... or it is disabled", open the link in the error, enable the API, wait a minute, then retry.
- **GA4**: For reporting you need a GA4 property ID. Use GA4 Admin API or the web UI to find it. Set `GA4_PROPERTY_ID` in `.env` when using `google_ga4.py`.
