"""
Compute free time slots from Google Calendar for booking purposes.

Reads configuration from environment variables (with sensible defaults):
- BOOKING_CALENDAR_ID (default: "primary")
- BOOKING_TIMEZONE (default: system local)
- BOOKING_WORKING_HOURS (e.g. "09:00-18:00")
- BOOKING_MEETING_LENGTH_MIN (e.g. "60")
- BOOKING_MIN_NOTICE_HOURS (e.g. "24")
- BOOKING_MAX_DAYS_AHEAD (e.g. "14")

Outputs a JSON document of the form:
{
  "generated_at": "ISO",
  "calendar_id": "...",
  "time_zone": "Asia/Hong_Kong",
  "meeting_length_minutes": 60,
  "slots": [
    { "start": "ISO", "end": "ISO" }
  ]
}

By default this is written to .tmp/calendar_availability.json and also printed
to stdout.
"""
import argparse
import json
import os
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.google_auth import get_credentials, run_oauth_flow  # type: ignore

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


def get_calendar_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def parse_hours_window(spec: str) -> (time, time):
    start_s, end_s = spec.split("-")
    sh, sm = map(int, start_s.split(":"))
    eh, em = map(int, end_s.split(":"))
    return time(sh, sm), time(eh, em)


def write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def collect_events(service, calendar_id: str, time_min: datetime, time_max: datetime) -> List[Dict]:
    events: List[Dict] = []
    page_token = None
    while True:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return events


def compute_free_slots(
    events: List[Dict],
    tz: ZoneInfo,
    meeting_length: timedelta,
    working_start: time,
    working_end: time,
    time_min: datetime,
    time_max: datetime,
    min_notice: timedelta,
) -> List[Dict[str, str]]:
    now = datetime.now(tz)
    earliest_start = now + min_notice

    # Normalize events into (start, end) in target tz
    busy: List[tuple[datetime, datetime]] = []
    for ev in events:
        start_raw = ev.get("start", {})
        end_raw = ev.get("end", {})
        if "dateTime" in start_raw:
            s = datetime.fromisoformat(start_raw["dateTime"])
        else:
            s = datetime.fromisoformat(start_raw["date"] + "T00:00:00+00:00")
        if "dateTime" in end_raw:
            e = datetime.fromisoformat(end_raw["dateTime"])
        else:
            e = datetime.fromisoformat(end_raw["date"] + "T00:00:00+00:00")
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        s = s.astimezone(tz)
        e = e.astimezone(tz)
        busy.append((s, e))

    busy.sort(key=lambda x: x[0])

    slots: List[Dict[str, str]] = []
    day = time_min.astimezone(tz).date()
    last_day = time_max.astimezone(tz).date()

    while day <= last_day:
        ws = datetime.combine(day, working_start, tz)
        we = datetime.combine(day, working_end, tz)
        if we <= earliest_start:
            day += timedelta(days=1)
            continue

        window_start = max(ws, earliest_start)
        window_end = we
        cursor = window_start

        for s, e in busy:
            if e <= cursor or s >= window_end:
                continue
            if s > cursor:
                while cursor + meeting_length <= s and cursor + meeting_length <= window_end:
                    slots.append(
                        {
                            "start": cursor.isoformat(),
                            "end": (cursor + meeting_length).isoformat(),
                        }
                    )
                    cursor += meeting_length
            cursor = max(cursor, e)

        while cursor + meeting_length <= window_end:
            slots.append(
                {
                    "start": cursor.isoformat(),
                    "end": (cursor + meeting_length).isoformat(),
                }
            )
            cursor += meeting_length

        day += timedelta(days=1)

    return slots


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute free time slots from Google Calendar for booking."
    )
    parser.add_argument(
        "--calendar-id",
        default=os.getenv("BOOKING_CALENDAR_ID", "primary"),
        help="Calendar ID to check (default from BOOKING_CALENDAR_ID or 'primary').",
    )
    parser.add_argument(
        "--days-ahead",
        type=int,
        default=int(os.getenv("BOOKING_MAX_DAYS_AHEAD", "14")),
        help="How many days ahead to search for availability.",
    )
    parser.add_argument(
        "--meeting-length-min",
        type=int,
        default=int(os.getenv("BOOKING_MEETING_LENGTH_MIN", "60")),
        help="Meeting length in minutes.",
    )
    parser.add_argument(
        "--working-hours",
        default=os.getenv("BOOKING_WORKING_HOURS", "09:00-18:00"),
        help='Daily working hours window, e.g. "09:00-18:00".',
    )
    parser.add_argument(
        "--time-zone",
        default=os.getenv("BOOKING_TIMEZONE", ""),
        help="IANA time zone (default: system local).",
    )
    parser.add_argument(
        "--min-notice-hours",
        type=int,
        default=int(os.getenv("BOOKING_MIN_NOTICE_HOURS", "24")),
        help="Minimum notice required before a slot can be offered.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(".tmp", "calendar_availability.json"),
        help="Output JSON file path.",
    )
    args = parser.parse_args()

    # Determine time zone:
    # - If explicitly provided, use that IANA zone.
    # - Otherwise, fall back to the system local tzinfo (which may be a plain
    #   datetime.timezone) or UTC as a last resort.
    if args.time_zone:
        tz = ZoneInfo(args.time_zone)
    else:
        local_tz = datetime.now().astimezone().tzinfo
        if isinstance(local_tz, timezone):
            tz = local_tz
        else:  # pragma: no cover - very rare environments
            tz = ZoneInfo("UTC")

    now = datetime.now(tz)
    time_min = now
    time_max = now + timedelta(days=args.days_ahead)

    working_start, working_end = parse_hours_window(args.working_hours)
    meeting_length = timedelta(minutes=args.meeting_length_min)
    min_notice = timedelta(hours=args.min_notice_hours)

    service = get_calendar_service()
    events = collect_events(
        service,
        calendar_id=args.calendar_id,
        time_min=time_min.astimezone(timezone.utc),
        time_max=time_max.astimezone(timezone.utc),
    )

    slots = compute_free_slots(
        events=events,
        tz=tz,
        meeting_length=meeting_length,
        working_start=working_start,
        working_end=working_end,
        time_min=time_min,
        time_max=time_max,
        min_notice=min_notice,
    )

    doc = {
        "generated_at": datetime.now(tz).isoformat(),
        "calendar_id": args.calendar_id,
        "time_zone": str(tz),
        "meeting_length_minutes": args.meeting_length_min,
        "slots": slots,
    }

    out_path = Path(args.output)
    write_json_atomic(out_path, doc)
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

