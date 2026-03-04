# Tools

Python scripts for deterministic execution: API calls, data transformations, file operations, database queries.

- Check existing tools before creating new ones.
- Credentials and API keys: use `.env` (never store secrets in code).
- Run from the project root using `py tools/<script>.py` (Windows) or `python tools/<script>.py`.

```powershell
cd d:\Agent
py -m pip install -r requirements.txt
py tools/google_auth.py
```

---

## Google APIs

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `google_auth.py` | OAuth2 flow — run once to generate `token.json` | `credentials.json` |
| `google_calendar.py` | List/create/delete calendar events | _(token.json)_ |
| `google_calendar_availability.py` | Query free/busy slots for booking proposals | `BOOKING_CALENDAR_ID`, `BOOKING_TIMEZONE`, `BOOKING_WORKING_HOURS_*` |
| `google_gmail.py` | Send/read Gmail messages | _(token.json)_ |
| `google_drive.py` | List files, upload CSV as Sheet (`--upload-csv`) | `GOOGLE_DRIVE_DEFAULT_FOLDER_ID` |
| `google_sheets.py` | Read/write Google Sheets | _(token.json)_ |
| `google_slides.py` | Create/update Google Slides presentations | _(token.json)_ |
| `google_ga4.py` | GA4 reporting — sessions, events, conversions (`--list-properties`) | `GA4_PROPERTY_ID` |

---

## Email Booking Agent

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `gmail_fetch_threads.py` | Fetch unread Gmail threads for processing | _(token.json)_ |
| `analyze_email_for_booking.py` | Classify emails as booking requests vs other | _(Claude API)_ |
| `thread_state_manager.py` | Track per-thread state (pending, proposed, confirmed) | _(local JSON)_ |
| `generate_time_proposals.py` | Generate available slot proposals from calendar | `BOOKING_*` vars |
| `draft_booking_email_reply.py` | Draft reply emails with time proposals | _(Claude API)_ |
| `create_calendar_event.py` | Create confirmed calendar events | `BOOKING_CALENDAR_ID` |
| `send_gmail_message.py` | Send drafted reply via Gmail API | _(token.json)_ |
| `log_bookings_to_google_sheet.py` | Log confirmed bookings to a tracking sheet | `BOOKING_LOG_SHEET_ID`, `BOOKING_LOG_SHEET_RANGE` |
| `booking_http_server.py` | HTTP server exposing booking agent as an endpoint | `BOOKING_AGENT_SECRET` |

See `workflows/booking/` for end-to-end SOPs.

---

## CRM / HubSpot

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `hubspot_api.py` | List/get contacts, companies, deals (`--contacts`, `--companies`, `--deals`, `--contact ID`, etc.) | `HUBSPOT_ACCESS_TOKEN` |
| `export_engagement_to_sheet.py` | Export HubSpot engagement data to a Google Sheet | `HUBSPOT_ACCESS_TOKEN` |

See `workflows/setup/hubspot_setup.md`.

---

## Meta

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `meta_insights_api.py` | Fetch Facebook/Instagram page insights via Graph API | `META_SYSTEM_USER_TOKEN`, `META_PAGE_ID`, `META_IG_BUSINESS_ID`, `META_GRAPH_API_VERSION` |
| `meta_audiences_api.py` | Create/manage Custom Audiences from CSV (hashed email upload, batch 10k). Commands: `list`, `create [--csv FILE --email-column COL]` | `META_SYSTEM_USER_TOKEN`, `META_AD_ACCOUNT_ID`, `META_GRAPH_API_VERSION` |

See `workflows/setup/meta_insights_setup.md` and `workflows/setup/meta_audience_create.md`.

---

## n8n Automation

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `n8n_api.py` | List workflows (`--workflows`), list executions (`--executions`), trigger webhook (`--trigger URL`), list registered webhook identities (`--webhook-urls`) | `N8N_BASE_URL`, `N8N_API_KEY` |

Webhook URL registry: `workflows/config/n8n_webhooks.json`. See `workflows/setup/n8n_setup.md`.

---

## WordPress / WooCommerce

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `wordpress_api.py` | CRUD for WordPress posts and pages | `WORDPRESS_URL`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` |
| `woocommerce_api.py` | Products, orders, update product (name/price/stock), check/adjust stock (`--stock`, `--adjust-stock`), sales reporting (`--sales-today`, `--sales-report`) | `WOOCOMMERCE_CONSUMER_KEY`, `WOOCOMMERCE_CONSUMER_SECRET` |
| `woo_report_one_time_2025.py` | One-time 2025 WooCommerce sales report export | _(same as above)_ |

See `workflows/setup/wordpress_setup.md`.

---

## Data / PII

| Script | Purpose | Key env vars |
|--------|---------|--------------|
| `hash_pii.py` | Hash email, tel, mobile, address in CSV/JSON. Use in pipelines or import `hash_record` / `hash_records` for in-process hashing. | `PII_HASH_SALT` (optional). Use `--no-salt` for Meta EMAIL_SHA256 compatibility. |
