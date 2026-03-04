"""
Google Drive API – list files and folders, upload CSV as Google Sheet.
Uses shared credentials from google_auth (run google_auth.py once).
When folder_id is not specified, uses GOOGLE_DRIVE_DEFAULT_FOLDER_ID from .env
(e.g. Shared drives\\Sales Department\\00_Inbox\\11_Inbox_Scott).
"""
import argparse
import os
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from dotenv import load_dotenv
from tools.google_auth import get_credentials, run_oauth_flow

load_dotenv(_ROOT / ".env")


def get_drive_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def list_files(service, page_size=20, order_by="modifiedTime desc", query=None):
    """List files; optional query (e.g. 'trashed = false')."""
    params = {"pageSize": page_size, "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)"}
    if order_by:
        params["orderBy"] = order_by
    if query:
        params["q"] = query
    result = service.files().list(**params).execute()
    return result.get("files", [])


def get_default_folder_id():
    """Folder ID for default uploads: Shared drives\\Sales Department\\00_Inbox\\11_Inbox_Scott."""
    return (os.getenv("GOOGLE_DRIVE_DEFAULT_FOLDER_ID") or "").strip() or None


def upload_csv_as_sheet(service, csv_path, title=None, folder_id=None):
    """
    Upload a local CSV file and convert it to a Google Sheet.
    If folder_id is not set, uses GOOGLE_DRIVE_DEFAULT_FOLDER_ID (e.g. 11_Inbox_Scott).
    Returns file dict with id, name, webViewLink.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    parent_id = folder_id or get_default_folder_id()
    file_metadata = {
        "name": title or path.stem,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]

    media = MediaFileUpload(str(path), mimetype="text/csv", resumable=False)
    kwargs = {"body": file_metadata, "media_body": media, "fields": "id,name,webViewLink"}
    if parent_id:
        kwargs["supportsAllDrives"] = True
    created = service.files().create(**kwargs).execute()
    return created


def main():
    parser = argparse.ArgumentParser(description="Google Drive – list files or upload CSV as Sheet")
    parser.add_argument("--list", action="store_true", help="List recent files")
    parser.add_argument("--upload-csv", metavar="FILE", help="Upload CSV and convert to Google Sheet")
    parser.add_argument("--title", help="Title for uploaded Sheet (optional)")
    parser.add_argument(
        "--folder-id",
        help="Drive folder ID (default: GOOGLE_DRIVE_DEFAULT_FOLDER_ID, e.g. 11_Inbox_Scott)",
    )
    parser.add_argument("-n", "--max", type=int, default=20, help="Max files to list")
    parser.add_argument(
        "-q",
        "--query",
        help="Drive query (e.g. \"mimeType='application/pdf'\" or \"'FOLDER_ID' in parents\")",
    )
    args = parser.parse_args()

    if not args.list and not args.upload_csv:
        parser.print_help()
        return 0

    service = get_drive_service()

    if args.list:
        for f in list_files(service, page_size=args.max, query=args.query):
            print(f.get("id", ""), f.get("name", "?"), f.get("mimeType", ""), f.get("modifiedTime", ""))

    if args.upload_csv:
        created = upload_csv_as_sheet(service, args.upload_csv, title=args.title, folder_id=args.folder_id)
        print(created.get("id", ""), created.get("name", ""), created.get("webViewLink", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
