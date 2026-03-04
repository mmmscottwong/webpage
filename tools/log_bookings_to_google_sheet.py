"""
Append a row describing a booking to a Google Sheet.

Inputs:
- --thread-id: Gmail threadId for which to log a booking.
- State: .tmp/thread_state/{thread_id}.json
- Event: .tmp/calendar_events/{thread_id}.json

Environment:
- BOOKING_LOG_SHEET_ID
- BOOKING_LOG_SHEET_RANGE (e.g. "Bookings!A:Z")

Appended row shape (columns are flexible; match your header row):
- timestamp (now, ISO 8601)
- threadId
- status
- confirmed_start
- confirmed_end
- event_link
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.google_sheets import append_rows  # type: ignore
from tools.google_sheets import get_sheets_service  # type: ignore


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Log a booking to a Google Sheet.")
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Gmail threadId to log.",
    )
    parser.add_argument(
        "--state-dir",
        default=os.path.join(".tmp", "thread_state"),
        help="Directory containing state JSON.",
    )
    parser.add_argument(
        "--events-dir",
        default=os.path.join(".tmp", "calendar_events"),
        help="Directory containing created event JSON.",
    )
    args = parser.parse_args()

    sheet_id = os.getenv("BOOKING_LOG_SHEET_ID")
    sheet_range = os.getenv("BOOKING_LOG_SHEET_RANGE")
    if not sheet_id or not sheet_range:
        raise SystemExit("BOOKING_LOG_SHEET_ID and BOOKING_LOG_SHEET_RANGE must be set in .env")

    state_path = Path(args.state_dir) / f"{args.thread_id}.json"
    event_path = Path(args.events_dir) / f"{args.thread_id}.json"
    if not state_path.exists() or not event_path.exists():
        raise SystemExit(f"Missing state or event JSON for thread {args.thread_id}")

    state = read_json(state_path)
    event = read_json(event_path)

    confirmed = state.get("confirmed_time") or {}
    confirmed_start = confirmed.get("start") or event.get("start", {}).get("dateTime", "")
    confirmed_end = confirmed.get("end") or event.get("end", {}).get("dateTime", "")
    event_link = event.get("htmlLink", "")

    row = [
        datetime.now(timezone.utc).isoformat(),
        args.thread_id,
        state.get("status", ""),
        confirmed_start,
        confirmed_end,
        event_link,
    ]

    service = get_sheets_service()
    append_rows(service, spreadsheet_id=sheet_id, range_notation=sheet_range, rows=[row])
    print("Logged booking to sheet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

