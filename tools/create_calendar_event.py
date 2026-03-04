"""
Create a Google Calendar event for a confirmed booking slot.

Inputs:
- --thread-id: Gmail threadId for context (used for logging only in this tool)
- --slot: ISO 8601 datetime for the event start (e.g. "2026-03-10T10:00:00+08:00")
- --duration: Duration in minutes (default 60)
- Optional analysis/state files to derive summary/attendees:
  - .tmp/email_analysis/{thread_id}.json

Outputs:
- Event JSON written to .tmp/calendar_events/{thread_id}.json and printed to stdout.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.google_auth import get_credentials, run_oauth_flow  # type: ignore


def get_calendar_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def read_json_if_exists(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pick_attendees(analysis: Optional[Dict]) -> List[Dict[str, str]]:
    if not analysis:
        return []
    attendees = []
    for p in analysis.get("participants", []):
        email = p.get("email")
        if not email:
            continue
        attendees.append({"email": email})
    return attendees


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Google Calendar event for a booking slot.")
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Gmail threadId associated with this booking.",
    )
    parser.add_argument(
        "--slot",
        required=True,
        help='Start datetime in ISO 8601 format, e.g. "2026-03-10T10:00:00+08:00".',
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in minutes (default 60).",
    )
    parser.add_argument(
        "--calendar-id",
        default=os.getenv("BOOKING_CALENDAR_ID", "primary"),
        help="Calendar ID (default from BOOKING_CALENDAR_ID or 'primary').",
    )
    parser.add_argument(
        "--analysis-dir",
        default=os.path.join(".tmp", "email_analysis"),
        help="Directory containing analysis JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(".tmp", "calendar_events"),
        help="Output directory for created event JSON.",
    )
    args = parser.parse_args()

    start_dt = datetime.fromisoformat(args.slot)
    end_dt = start_dt + timedelta(minutes=args.duration)

    analysis = read_json_if_exists(Path(args.analysis_dir) / f"{args.thread_id}.json")
    attendees = pick_attendees(analysis)

    summary = "Booking"
    if analysis and analysis.get("summary"):
        summary = analysis["summary"]

    event_body = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }
    if attendees:
        event_body["attendees"] = attendees

    service = get_calendar_service()
    created = (
        service.events()
        .insert(calendarId=args.calendar_id, body=event_body, sendUpdates="all")
        .execute()
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.thread_id}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(created, f, ensure_ascii=False, indent=2)

    print(json.dumps(created, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

