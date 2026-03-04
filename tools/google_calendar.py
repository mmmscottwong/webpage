"""
Google Calendar API – list calendars and events.
Uses shared credentials from google_auth (run google_auth.py once).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from tools.google_auth import get_credentials, run_oauth_flow


def get_calendar_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def list_calendars(service):
    """Return list of calendar list entries (id, summary)."""
    result = service.calendarList().list().execute()
    return result.get("items", [])


def list_upcoming_events(service, calendar_id="primary", max_results=10):
    """Return upcoming events for the given calendar."""
    now = datetime.now(timezone.utc).isoformat()
    events = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events.get("items", [])


def main():
    parser = argparse.ArgumentParser(description="Google Calendar – list calendars or upcoming events")
    parser.add_argument("--calendars", action="store_true", help="List calendar names and IDs")
    parser.add_argument("--upcoming", action="store_true", help="List upcoming events (primary calendar)")
    parser.add_argument("--calendar-id", default="primary", help="Calendar ID for --upcoming")
    parser.add_argument("-n", "--max-results", type=int, default=10, help="Max events for --upcoming")
    args = parser.parse_args()

    if not args.calendars and not args.upcoming:
        parser.print_help()
        return 0

    service = get_calendar_service()
    if args.calendars:
        for cal in list_calendars(service):
            print(cal.get("summary", "?") + "\t" + cal.get("id", ""))
    if args.upcoming:
        for ev in list_upcoming_events(service, args.calendar_id, args.max_results):
            start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "?")
            print(start, ev.get("summary", "(no title)"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
