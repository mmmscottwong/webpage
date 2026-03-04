"""
Google Sheets API – read and write spreadsheets.
Uses shared credentials from google_auth (run google_auth.py once).
"""
import argparse
import sys
from pathlib import Path

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from tools.google_auth import get_credentials, run_oauth_flow


def get_sheets_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("sheets", "v4", credentials=creds)


def read_range(service, spreadsheet_id, range_notation):
    """Read a range (e.g. 'Sheet1!A1:D10'). Returns list of rows."""
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_notation).execute()
    return result.get("values", [])


def append_rows(service, spreadsheet_id, range_notation, rows, value_input_option="USER_ENTERED"):
    """Append rows to a sheet. range_notation e.g. 'Sheet1!A:D'."""
    body = {"values": rows}
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueInputOption=value_input_option,
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()


def create_spreadsheet(title, sheet_name="Sheet1"):
    """Create a new spreadsheet. Returns dict with spreadsheetId, spreadsheetUrl."""
    service = get_sheets_service()
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": sheet_name}}],
    }
    result = service.spreadsheets().create(body=body).execute()
    return {"spreadsheetId": result["spreadsheetId"], "spreadsheetUrl": result["spreadsheetUrl"]}


def update_range(service, spreadsheet_id, range_notation, rows, value_input_option="USER_ENTERED"):
    """Write (overwrite) a range. range_notation e.g. 'Sheet1!A1:H1000'."""
    body = {"values": rows}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueInputOption=value_input_option,
        body=body,
    ).execute()


def main():
    parser = argparse.ArgumentParser(description="Google Sheets – read or append")
    parser.add_argument("--read", action="store_true", help="Read a range")
    parser.add_argument("--spreadsheet-id", required=True, help="Spreadsheet ID (from URL)")
    parser.add_argument("--range", default="Sheet1!A1:Z1000", help="A1 notation range")
    parser.add_argument("--append", nargs="+", metavar="ROW", help="Append a row (space-separated values)")
    args = parser.parse_args()

    if not args.read and not args.append:
        parser.print_help()
        return 0

    service = get_sheets_service()
    if args.read:
        for row in read_range(service, args.spreadsheet_id, args.range):
            print("\t".join(str(c) for c in row))
    if args.append:
        append_rows(service, args.spreadsheet_id, args.range, [args.append])
        print("Appended.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
