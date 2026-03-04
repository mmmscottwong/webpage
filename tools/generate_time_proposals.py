"""
Generate concrete time proposals for a booking thread based on analysis and availability.

Inputs:
- Analysis: .tmp/email_analysis/{thread_id}.json
- State: .tmp/thread_state/{thread_id}.json
- Availability: .tmp/calendar_availability.json (from google_calendar_availability.py)

Outputs:
- .tmp/time_proposals/{thread_id}.json with:
  {
    "threadId": "...",
    "proposed_slots": [
      { "start": "ISO", "end": "ISO" }
    ]
  }
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def generate_for_thread(
    thread_id: str,
    analysis_dir: Path,
    state_dir: Path,
    availability: Dict,
    max_slots: int,
    output_dir: Path,
) -> None:
    analysis_path = analysis_dir / f"{thread_id}.json"
    state_path = state_dir / f"{thread_id}.json"
    if not analysis_path.exists() or not state_path.exists():
        return

    analysis = read_json(analysis_path)
    state = read_json(state_path)

    already_proposed = {
        (p.get("start"), p.get("end"))
        for p in state.get("last_proposed_times", [])
        if p.get("start") and p.get("end")
    }

    proposed_slots: List[Dict[str, str]] = []
    for slot in availability.get("slots", []):
        key = (slot.get("start"), slot.get("end"))
        if key in already_proposed:
            continue
        proposed_slots.append({"start": slot["start"], "end": slot["end"]})
        if len(proposed_slots) >= max_slots:
            break

    doc = {
        "threadId": thread_id,
        "proposed_slots": proposed_slots,
    }
    out_path = output_dir / f"{thread_id}.json"
    write_json_atomic(out_path, doc)
    print(f"Wrote {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate concrete time proposals for a booking thread."
    )
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Gmail threadId to generate proposals for.",
    )
    parser.add_argument(
        "--analysis-dir",
        default=os.path.join(".tmp", "email_analysis"),
        help="Directory containing analysis JSON.",
    )
    parser.add_argument(
        "--state-dir",
        default=os.path.join(".tmp", "thread_state"),
        help="Directory containing state JSON.",
    )
    parser.add_argument(
        "--availability-file",
        default=os.path.join(".tmp", "calendar_availability.json"),
        help="Path to calendar availability JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(".tmp", "time_proposals"),
        help="Output directory for proposals.",
    )
    parser.add_argument(
        "--max-slots",
        type=int,
        default=int(os.getenv("BOOKING_PROPOSE_SLOTS", "3")),
        help="Maximum number of slots to propose.",
    )
    args = parser.parse_args()

    availability_path = Path(args.availability_file)
    if not availability_path.exists():
        raise SystemExit(f"Availability file not found: {availability_path}")
    availability = read_json(availability_path)

    generate_for_thread(
        thread_id=args.thread_id,
        analysis_dir=Path(args.analysis_dir),
        state_dir=Path(args.state_dir),
        availability=availability,
        max_slots=args.max_slots,
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

