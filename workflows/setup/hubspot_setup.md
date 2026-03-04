# Workflow: Connect HubSpot

## Objective
Enable the project to call HubSpot’s CRM API (contacts, companies, deals) using a Private App access token.

## Required inputs
- **HubSpot account** where you are a super admin (or have permission to create Private Apps).
- **Private App** with an access token and the scopes you need (e.g. `crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.deals.read`; add `write` for create/update).

## Tools to use
- `tools/hubspot_api.py` — list and get contacts, companies, deals; optional create/update. Uses `HUBSPOT_ACCESS_TOKEN` from `.env`. Also supports **CRM segmentation**: yesterday’s engagement list via Search API.

## Steps

### 1. Create a Private App and get the token
1. In HubSpot: **Settings** (gear) → **Integrations** → **Private Apps**.
2. **Create a private app** — name it (e.g. `Agent`).
3. Under **Scopes**, add the scopes you need, for example:
   - `crm.objects.contacts.read` / `crm.objects.contacts.write`
   - `crm.objects.companies.read` / `crm.objects.companies.write`
   - `crm.objects.deals.read` / `crm.objects.deals.write`
4. **Create app** and copy the **Access token** (shown once). Store it in `.env` as `HUBSPOT_ACCESS_TOKEN`.

### 2. Add to `.env`
```env
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

(Use the token from the Private App; it often starts with `pat-`.)

### 3. Verify
From project root (Windows Terminal):

```powershell
py tools/hubspot_api.py --contacts -n 5
py tools/hubspot_api.py --companies -n 5
py tools/hubspot_api.py --deals -n 5
```

## Expected outputs
- `--contacts` lists recent contacts (email, name, etc.).
- `--companies` lists companies.
- `--deals` lists deals (name, stage, amount, etc.).
- `--engagement-yesterday` lists contacts with engagement (or record update) in the last calendar day; use for CRM segmentation and trend insight.

---

## CRM segmentation: yesterday’s engagement list

**Objective:** Get a list of contacts who had engagement yesterday (email opens/clicks, form submissions, meetings, notes, etc.) for insight and trend analysis.

**Tool:** `tools/hubspot_api.py`

**Commands (from project root):**

```powershell
# List yesterday’s engagement contacts (default up to 1000)
py tools/hubspot_api.py --engagement-yesterday -n 500

# Save full list to JSON for reporting or further analysis
py tools/hubspot_api.py --engagement-yesterday -n 5000 -o .tmp/yesterday_engagement.json
```

**Behaviour:**
- Uses HubSpot **CRM Search API** to filter contacts by engagement/activity date.
- Tries `hs_lastengagementdate` first (email opens, form submissions, meeting bookings, etc.); falls back to `lastmodifieddate` (any contact record update) if needed.
- Output: contact ID, email, firstname, lastname, company, and last engagement/modified timestamp. With `-o`, writes full contact objects (including all requested properties) to the given path.
- `.tmp/` is for intermediates; move or send final lists to Sheets/Slides/etc. as needed.

**Insight and trends:** Run daily (e.g. via scheduler or n8n), compare list size over time, or join with deal/company data for segmentation.

**Data / analysis (Google Sheet or Doc):** For work-ready output, use **Google Sheet** (or Doc) instead of raw JSON. From project root:

```powershell
# 1. Get yesterday engagement and save JSON
py tools/hubspot_api.py --engagement-yesterday -n 5000 -o .tmp/yesterday_engagement.json

# 2. Export to CSV (always) and optionally to a new Google Sheet
py tools/export_engagement_to_sheet.py
```

- **CSV** is always written to `.tmp/yesterday_engagement.csv` — open in Excel or **upload to Google Sheets** (File → Import → Upload).
- **Google Sheet** (new spreadsheet created automatically) requires the **Google Sheets API** to be enabled once in [Google Cloud Console](https://console.developers.google.com/apis/api/sheets.googleapis.com/overview). After enabling, re-run the export script to get a direct Sheet link.
- Prefer Sheet/Doc for sharing and analysis; keep JSON/CSV only as intermediates.

**Upload to Shared Drive (default folder):** To save the engagement list into **Shared drives\\Sales Department\\00_Inbox\\11_Inbox_Scott** with a standard name:

1. Set `GOOGLE_DRIVE_DEFAULT_FOLDER_ID` in `.env` to the folder ID of `11_Inbox_Scott` (copy from the folder’s URL in Drive).
2. Run:
   ```powershell
   py tools/hubspot_api.py --engagement-yesterday -n 5000 -o .tmp/yesterday_engagement.json
   py tools/export_engagement_to_sheet.py --upload-to-drive
   ```
   The file is uploaded as a Google Sheet named **Hubspot_EngagementList_Yesterday_YYYYMMDD** (e.g. `Hubspot_EngagementList_Yesterday_20260303`). Use this naming pattern for other outputs when not specified: `{Source}_{Description}_{YYYYMMDD}`.

## Contacts who purchased in a month (HubSpot only)

**Objective:** List contacts who have at least one **deal (order) closed** in a given month, using **only HubSpot** data (no WooCommerce). Useful for “online store” purchasers in a specific month (e.g. December 2025).

**Tools:** `tools/hubspot_api.py` (API), `tools/hubspot_report_purchasers.py` (report script).

**Commands (from project root):**

```powershell
# Report: contacts with a deal closed in Dec 2025 (CSV to .tmp)
py tools/hubspot_report_purchasers.py --month 2025-12

# Optional: restrict to a pipeline (e.g. online store) if your account uses pipeline ID
py tools/hubspot_report_purchasers.py --month 2025-12 --pipeline-id YOUR_PIPELINE_ID

# Upload the CSV as a Google Sheet to the default Drive folder (11_Inbox_Scott)
py tools/hubspot_report_purchasers.py --month 2025-12 --upload-to-drive
```

**Behaviour:**
- Searches **deals** by `closedate` in the given month, then resolves **deal → contact** associations and fetches contact properties (email, first name, last name, company, phone).
- **CSV** is written to `.tmp/Hubspot_ContactsPurchased_YYYYMM.csv` (e.g. `Hubspot_ContactsPurchased_202512.csv`). With `--upload-to-drive`, the file is uploaded as a Sheet named **Hubspot_ContactsPurchased_YYYYMM_YYYYMMDD** to the default folder (same as engagement list).
- **“Online store”:** If all deals in that month are from the online store, no extra filter is needed. If you use a specific **pipeline** for online store, pass `--pipeline-id` with that pipeline’s ID (find it in HubSpot: Deals → Pipeline settings, or via API).

**Quick check via API only:**

```powershell
py tools/hubspot_api.py --contacts-purchased-in-month 2025-12 -o .tmp/contacts_202512.json
```

This prints the contact count and tab-separated list; use `-o` to save full JSON.

## Edge cases / notes
- **Token** is account-specific; never commit it. Keep it only in `.env`.
- **Rate limits**: HubSpot has rate limits per app; use reasonable `-n` and avoid huge bursts.
- **Pagination**: For more than 100 records, the tool uses the `after` cursor automatically when you request a larger `-n`.
- **403 / 401**: Check that the Private App has the right scopes and the token is correct. Regenerate the token in HubSpot if needed.
