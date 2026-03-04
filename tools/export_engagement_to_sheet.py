"""
Export HubSpot yesterday-engagement list (JSON) to Google Sheet or CSV for analysis.
- CSV: always written to .tmp/ (open in Excel or upload to Google Sheets).
- Google Sheet: upload via Drive (--upload-to-drive) to default folder with naming:
  Hubspot_EngagementList_Yesterday_YYYYMMDD (uses GOOGLE_DRIVE_DEFAULT_FOLDER_ID).
Also enriches each contact with approximate engagement kind, traffic source fields, and (when available)
last email engagement details (subject, direction, status, to/from).
Run from project root: py tools/export_engagement_to_sheet.py [path/to/engagement.json]
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def engagement_rows_from_json(data, email_summaries=None):
    """Build [header_row] + data rows from HubSpot engagement contact list."""
    header = [
        "Contact ID",
        "Email",
        "First name",
        "Last name",
        "Company",
        "Phone",
        "Last engagement / updated",
        "Engagement kind (approx)",
        "Original source",
        "Original source detail 1",
        "Original source detail 2",
        "Latest source",
        "Latest source detail 1",
        "Latest source detail 2",
        "Last email subject (yesterday)",
        "Last email status",
        "Last email direction",
        "Last email to",
        "Last email from",
        "HubSpot URL",
    ]
    rows = [header]
    for c in data:
        props = c.get("properties", {}) or {}
        last_engagement = props.get("hs_lastengagementdate")
        last_modified = props.get("lastmodifieddate")
        last_sales_activity = props.get("hs_last_sales_activity_date")
        last_activity = last_engagement or last_modified or last_sales_activity or ""

        if last_engagement:
            engagement_kind = "Engagement (email / form / meeting / etc.)"
        elif last_sales_activity:
            engagement_kind = "Sales activity"
        elif last_modified:
            engagement_kind = "Record update"
        else:
            engagement_kind = ""

        contact_id = str(c.get("id", ""))
        es = (email_summaries or {}).get(contact_id, {})
        rows.append([
            contact_id,
            (props.get("email") or ""),
            (props.get("firstname") or ""),
            (props.get("lastname") or ""),
            (props.get("company") or ""),
            (props.get("phone") or ""),
            str(last_activity),
            engagement_kind,
            (props.get("hs_analytics_source") or ""),
            (props.get("hs_analytics_source_data_1") or ""),
            (props.get("hs_analytics_source_data_2") or ""),
            (props.get("hs_analytics_latest_source") or ""),
            (props.get("hs_analytics_latest_source_data_1") or ""),
            (props.get("hs_analytics_latest_source_data_2") or ""),
            (es.get("hs_email_subject") or ""),
            (es.get("hs_email_status") or ""),
            (es.get("hs_email_direction") or ""),
            (es.get("hs_email_to_email") or ""),
            (es.get("hs_email_from_email") or ""),
            c.get("url", ""),
        ])
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export engagement JSON to Google Sheet or CSV (with extra fields)")
    parser.add_argument(
        "json_path",
        nargs="?",
        default=_ROOT / ".tmp" / "yesterday_engagement.json",
        help="Path to engagement JSON (default: .tmp/yesterday_engagement.json)",
    )
    parser.add_argument("--title", default="", help="Sheet title (default: Yesterday engagement N contacts)")
    parser.add_argument("--csv-only", action="store_true", help="Only write CSV to .tmp (no upload)")
    parser.add_argument(
        "--upload-to-drive",
        action="store_true",
        help="Upload CSV as Google Sheet to default folder (Hubspot_EngagementList_Yesterday_YYYYMMDD)",
    )
    args = parser.parse_args()

    path = Path(args.json_path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]

    # Try to enrich with last email engagement details from HubSpot (yesterday only)
    email_summaries = {}
    try:
        from tools.hubspot_api import get_yesterday_email_engagement_summaries

        email_summaries = get_yesterday_email_engagement_summaries()
    except Exception as e:
        print(
            f"Warning: could not load email engagement details; email columns will be blank. ({e})",
            file=sys.stderr,
        )

    rows = engagement_rows_from_json(data, email_summaries=email_summaries)
    if len(rows) <= 1:
        print("No contact rows to export.", file=sys.stderr)
        return 1

    # Always write CSV to .tmp for analysis (Excel / upload to Sheets)
    csv_path = _ROOT / ".tmp" / "yesterday_engagement.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"CSV: {csv_path} ({len(rows) - 1} contacts)", file=sys.stderr)

    if args.upload_to_drive:
        try:
            from tools.google_drive import get_default_folder_id, get_drive_service, upload_csv_as_sheet

            title = f"Hubspot_EngagementList_Yesterday_{date.today().strftime('%Y%m%d')}"
            service = get_drive_service()
            folder_id = get_default_folder_id()
            created = upload_csv_as_sheet(service, csv_path, title=title, folder_id=folder_id)
            print(created.get("webViewLink", ""))
            print(f"Uploaded as: {created.get('name')}", file=sys.stderr)
        except Exception as e:
            print(f"Upload failed: {e}", file=sys.stderr)
            return 1
        return 0

    if args.csv_only:
        print(str(csv_path))
        return 0

    try:
        from tools.google_sheets import get_sheets_service, create_spreadsheet, update_range
    except ImportError:
        print("Google Sheet export skipped (tools not available). Use CSV or --csv-only.", file=sys.stderr)
        print(str(csv_path))
        return 0

    title = args.title or f"Yesterday engagement ({len(rows) - 1} contacts)"
    try:
        created = create_spreadsheet(title, sheet_name="Contacts")
        sid = created["spreadsheetId"]
        url = created["spreadsheetUrl"]
        service = get_sheets_service()
        end_row = len(rows)
        num_cols = len(rows[0])
        col_end = chr(ord("A") + num_cols - 1) if num_cols <= 26 else "Z"
        range_notation = f"Contacts!A1:{col_end}{end_row}"
        update_range(service, sid, range_notation, rows)
        print(url)
        print(f"Exported {len(rows) - 1} contacts to Google Sheet.", file=sys.stderr)
    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "SERVICE_DISABLED" in err_str or "has not been used" in err_str:
            print(
                "Google Sheets API is disabled. Enable it in Google Cloud Console, then run again:",
                file=sys.stderr,
            )
            print("  https://console.developers.google.com/apis/api/sheets.googleapis.com/overview", file=sys.stderr)
            print("Using CSV for now. Upload to Google Sheets: File → Import → Upload → select the CSV.", file=sys.stderr)
            print(str(csv_path))
        else:
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
