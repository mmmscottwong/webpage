# Workflow: Create Meta Custom Audience from CSV

## Objective

Create a **Custom Audience** in Meta (Facebook/Instagram) Ads from a CSV of emails, so it can be used for ad targeting in Ads Manager. The agent runs the tool; you provide audience name and CSV path (and optional column name).

---

## 1. Required inputs

- **Audience name** – e.g. "Newsletter subscribers 2025-03"
- **CSV file path** – e.g. `.tmp/contacts.csv`, with at least one column of email addresses
- **Email column name** (optional) – default is `email`; use `--email-column` if your CSV uses another header (e.g. `Email`, `email_address`)

### 1.1 Environment and permissions

- **`.env`** must include:
  - `META_SYSTEM_USER_TOKEN` – System User token with **ads_management** (and often **business_management**) scope. Same token as for insights can be used if these scopes are added.
  - `META_AD_ACCOUNT_ID` – Ad Account ID (e.g. `act_123456789`). From Ads Manager → Account Settings, or from Graph API `me/adaccounts`.
- Optional: `META_GRAPH_API_VERSION` (defaults to `v18.0`).

---

## 2. Tool: `tools/meta_audiences_api.py`

Run from project root (e.g. `d:\Agent`).

### 2.1 List existing custom audiences

```powershell
py tools/meta_audiences_api.py list
```

Output: tab-separated table of `id`, `name`, `subtype`, `approximate_count`.

### 2.2 Create a custom audience (empty)

```powershell
py tools/meta_audiences_api.py create --name "My Audience Name" [--description "Optional description"]
```

Prints the new audience ID.

### 2.3 Create a custom audience and add users from CSV

```powershell
py tools/meta_audiences_api.py create --name "Newsletter 2025-03" --csv .tmp/contacts.csv [--email-column email]
```

- Reads the CSV, normalizes emails (trim, lowercase), deduplicates, hashes with SHA256, and uploads in batches of 10,000.
- Prints audience ID and number of emails uploaded.
- Use `--email-column` if the column is not named `email` (e.g. `--email-column Email`).

---

## 3. Agent usage

When the user asks to **create a Meta audience list** (or "create custom audience from this CSV"):

1. Confirm audience name and CSV path (and column name if not `email`).
2. Run:  
   `py tools/meta_audiences_api.py create --name "<name>" --csv "<path>" [--email-column "<col>"]`
3. Report the audience ID and that it can be used in Ads Manager for targeting.
4. Optional: if the user asked for the list in Drive or email, use the existing deliver-to-Drive/email flow with the same CSV or a summary.

---

## 4. Constraints and notes

- **Hashing**: Emails are normalized (trim, lowercase) and hashed with SHA256 before upload; the tool does this. Do not pre-hash the CSV.
- **Rate / size**: Up to 10,000 users per API request; the tool batches automatically. Large files may take a while.
- **Processing time**: Meta typically takes up to 24 hours to process audience updates.
- **Policy**: Custom audiences that suggest sensitive data (e.g. health, financial) may be flagged (`operation_status` 471) and restricted; avoid naming or describing audiences in a way that implies such data. See [Meta’s Custom Audience terms](https://developers.facebook.com/docs/marketing-api/audiences-api/custom-audience-terms-of-service).
- **Phone column**: The tool currently supports email only. Phone (PHONE_SHA256) can be added later if needed; normalization would strip non-digits.

---

## 5. Errors

- **Set META_AD_ACCOUNT_ID in .env** – Add the Ad Account ID (e.g. `act_123456789`).
- **Permissions error (200)** – Token needs `ads_management` (and possibly `business_management`) in Business Suite → System Users.
- **Column 'X' not found** – Use `--email-column` with the exact CSV header name.
- **Audience Upload Blocked / operation_status 471** – Audience was flagged; see Meta’s Audience Manager or create a new audience with different naming/data.
