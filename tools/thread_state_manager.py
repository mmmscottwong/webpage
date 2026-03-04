"""
Maintain per-thread booking state for the email booking agent.

Inputs:
- Thread snapshots: .tmp/email_threads/{thread_id}.json
- Analysis results: .tmp/email_analysis/{thread_id}.json

Outputs:
- State files at .tmp/thread_state/{thread_id}.json with shape:
  {
    "threadId": "...",
    "status": "new_request" | "times_proposed" | "waiting_for_client" | "confirmed" | "cancelled",
    "intent": "booking_new" | "reschedule" | "cancel" | "not_booking",
    "last_message_id": "...",
    "last_message_ts": "ISO 8601 UTC timestamp",
    "last_proposed_times": [
      { "start": "ISO", "end": "ISO" }
    ],
    "confirmed_time": { "start": "ISO", "end": "ISO" } | null,
    "history": [
      { "timestamp": "ISO", "event": "status_change", "from": "new_request", "to": "times_proposed" }
    ]
  }

The state files are append-only logs of the booking lifecycle for each Gmail thread.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def iso_utc_from_ms(ms: str) -> str:
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def latest_message_info(thread_doc: Dict) -> Dict[str, str]:
    messages = thread_doc.get("messages", [])
    if not messages:
        now = datetime.now(timezone.utc).isoformat()
        return {"id": "", "ts": now}
    latest = sorted(messages, key=lambda m: int(m.get("internalDate") or 0), reverse=True)[0]
    return {
        "id": latest.get("id", ""),
        "ts": iso_utc_from_ms(latest.get("internalDate") or "0"),
    }


def update_status(prev_status: Optional[str], intent: str) -> str:
    if intent == "cancel":
        return "cancelled"
    if intent == "reschedule":
        return "new_request"
    if intent == "booking_new":
        if prev_status in {"times_proposed", "waiting_for_client"}:
            return prev_status
        return "new_request"
    # not_booking
    return prev_status or "not_booking"


def process_thread_state(
    thread_path: Path,
    analysis_dir: Path,
    state_dir: Path,
    update_only: bool = False,
) -> None:
    thread_doc = read_json(thread_path)
    thread_id = thread_doc.get("threadId") or thread_path.stem
    analysis_path = analysis_dir / f"{thread_id}.json"
    if not analysis_path.exists():
        if update_only:
            return
        intent = "not_booking"
        analysis = {"intent": intent}
    else:
        analysis = read_json(analysis_path)
        intent = analysis.get("intent", "not_booking")

    state_path = state_dir / f"{thread_id}.json"
    if state_path.exists():
        state = read_json(state_path)
    else:
        state = {
            "threadId": thread_id,
            "status": "new_request",
            "intent": intent,
            "last_message_id": "",
            "last_message_ts": "",
            "last_proposed_times": [],
            "confirmed_time": None,
            "history": [],
        }

    latest = latest_message_info(thread_doc)
    prev_status = state.get("status")
    new_status = update_status(prev_status, intent)

    if new_status != prev_status:
        state.setdefault("history", []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "status_change",
                "from": prev_status,
                "to": new_status,
            }
        )

    state["status"] = new_status
    state["intent"] = intent
    state["last_message_id"] = latest["id"]
    state["last_message_ts"] = latest["ts"]

    write_json_atomic(state_path, state)
    print(f"Wrote {state_path}")


def process_all(
    threads_dir: Path,
    analysis_dir: Path,
    state_dir: Path,
    update_only: bool = False,
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    for thread_path in sorted(threads_dir.glob("*.json")):
        process_thread_state(thread_path, analysis_dir, state_dir, update_only=update_only)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Maintain per-thread booking state for Gmail booking threads."
    )
    parser.add_argument(
        "--threads-dir",
        default=os.path.join(".tmp", "email_threads"),
        help="Directory containing thread JSON snapshots.",
    )
    parser.add_argument(
        "--analysis-dir",
        default=os.path.join(".tmp", "email_analysis"),
        help="Directory containing analysis JSON files.",
    )
    parser.add_argument(
        "--state-dir",
        default=os.path.join(".tmp", "thread_state"),
        help="Output directory for per-thread state JSON.",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="If set, skip threads that have no analysis file.",
    )
    args = parser.parse_args()

    threads_dir = Path(args.threads_dir)
    if not threads_dir.exists():
        raise SystemExit(f"Threads dir not found: {threads_dir}")

    process_all(
        threads_dir=threads_dir,
        analysis_dir=Path(args.analysis_dir),
        state_dir=Path(args.state_dir),
        update_only=bool(args.update_only),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

