"""
HubSpot report: contacts who made at least one purchase (deal closed) in a given month.
Uses only HubSpot data (deals + deal–contact associations + contact properties).
Output: CSV to .tmp/Hubspot_ContactsPurchased_YYYYMM.csv; optional upload as Google Sheet to default Drive folder.
Run from project root: py tools/hubspot_report_purchasers.py --month 2025-12 [--pipeline-id ID] [--upload-to-drive]
"""
import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _last_day_of_month(year: int, month: int) -> str:
    """Return YYYY-MM-DD for the last day of the given month."""
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    last = end - timedelta(days=1)
    return last.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(
        description="List contacts with at least one deal closed in a month (HubSpot only)"
    )
    parser.add_argument("--month", required=True, metavar="YYYY-MM", help="Month, e.g. 2025-12")
    parser.add_argument(
        "--pipeline-id",
        type=str,
        metavar="ID",
        help="Optional pipeline ID to restrict to (e.g. online store)",
    )
    parser.add_argument(
        "--upload-to-drive",
        action="store_true",
        help="Upload CSV as Google Sheet to default folder (Hubspot_ContactsPurchased_YYYYMM_YYYYMMDD)",
    )
    args = parser.parse_args()

    try:
        parts = args.month.strip().split("-")
        year, month = int(parts[0]), int(parts[1])
        if not (1 <= month <= 12):
            raise ValueError("month must be 1-12")
        from_date = f"{year:04d}-{month:02d}-01"
        to_date = _last_day_of_month(year, month)
    except (ValueError, IndexError) as e:
        print(f"Error: --month must be YYYY-MM (e.g. 2025-12). {e}", file=sys.stderr)
        return 1

    pipeline_id = args.pipeline_id.strip() if args.pipeline_id else None

    from tools.hubspot_api import get_contacts_with_deals_closed_in_range

    contacts = get_contacts_with_deals_closed_in_range(from_date, to_date, pipeline_id=pipeline_id)

    header = [
        "Contact ID",
        "Email",
        "First name",
        "Last name",
        "Company",
        "Phone",
    ]
    rows = [header]
    for c in contacts:
        props = c.get("properties", {}) or {}
        rows.append([
            str(c.get("id", "")),
            props.get("email") or "",
            props.get("firstname") or "",
            props.get("lastname") or "",
            props.get("company") or "",
            props.get("phone") or "",
        ])

    yyyymm = f"{year:04d}{month:02d}"
    csv_name = f"Hubspot_ContactsPurchased_{yyyymm}.csv"
    csv_path = _ROOT / ".tmp" / csv_name
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"CSV: {csv_path} ({len(rows) - 1} contacts)", file=sys.stderr)

    if args.upload_to_drive:
        try:
            from tools.google_drive import get_default_folder_id, get_drive_service, upload_csv_as_sheet
        except ImportError:
            print("Upload skipped: google_drive not available.", file=sys.stderr)
            return 0
        title = f"Hubspot_ContactsPurchased_{yyyymm}_{date.today().strftime('%Y%m%d')}"
        try:
            service = get_drive_service()
            folder_id = get_default_folder_id()
            created = upload_csv_as_sheet(service, csv_path, title=title, folder_id=folder_id)
            print(created.get("webViewLink", ""))
            print(f"Uploaded as: {created.get('name')}", file=sys.stderr)
        except Exception as e:
            print(f"Upload failed: {e}", file=sys.stderr)
            return 1

    print(str(csv_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
