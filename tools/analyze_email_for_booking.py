"""
Analyse Gmail thread snapshots and infer booking intent and basic details.

Inputs:
- Thread snapshot JSON files from .tmp/email_threads/{thread_id}.json
  (produced by gmail_fetch_threads.py)

Outputs:
- One JSON file per thread at .tmp/email_analysis/{thread_id}.json:
  {
    "threadId": "...",
    "intent": "booking_new" | "reschedule" | "cancel" | "not_booking",
    "requested_time_windows": [
      { "text": "next week morning", "confidence": 0.5 }
    ],
    "participants": [
      { "name": "Client Name", "email": "client@example.com", "role": "client" }
    ],
    "duration_minutes": 60,
    "language": "en",
    "summary": "Short plain-language summary of what the guest is asking."
  }

This implementation uses simple heuristics (keywords and headers) so it works
without any external LLM. You can later swap the core analysis with your own
LLM endpoint while keeping the same input/output JSON shape.
"""
import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional


def read_thread(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def guess_intent(text: str) -> str:
    lowered = text.lower()
    if any(w in lowered for w in ["reschedule", "re-schedule", "change the time", "move our meeting"]):
        return "reschedule"
    if any(w in lowered for w in ["cancel", "call off", "no longer able to", "can't make it"]):
        return "cancel"
    if any(w in lowered for w in ["book", "booking", "appointment", "consultation", "schedule a call"]):
        return "booking_new"
    return "not_booking"


def guess_language(text: str) -> str:
    # Extremely simple heuristic to distinguish English vs likely Chinese.
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def extract_participants(messages: List[Dict]) -> List[Dict]:
    participants: Dict[str, Dict[str, str]] = {}
    for m in messages:
        headers = m.get("headers", {})
        for key in ("From", "To", "Cc"):
            raw = headers.get(key) or ""
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                # Very simple email extraction: Name <email@example.com>
                match = re.search(r"(.*?)(<([^>]+)>)", part)
                if match:
                    name = match.group(1).strip().strip('"') or ""
                    email = match.group(3).strip()
                else:
                    name = ""
                    email = part
                if email not in participants:
                    participants[email] = {"name": name, "email": email, "role": "unknown"}
    return list(participants.values())


def build_summary(subject: str, body: str) -> str:
    body_line = body.strip().splitlines()[0] if body.strip() else ""
    if subject and body_line:
        return f"{subject.strip()} — {body_line[:160]}"
    return subject or body_line[:160]


def analyse_thread(thread_doc: Dict) -> Dict:
    thread_id = thread_doc.get("threadId")
    messages = thread_doc.get("messages", [])
    if not messages:
        return {
            "threadId": thread_id,
            "intent": "not_booking",
            "requested_time_windows": [],
            "participants": [],
            "duration_minutes": 60,
            "language": "en",
            "summary": "",
        }

    latest: Dict = sorted(
        messages,
        key=lambda m: int(m.get("internalDate") or 0),
        reverse=True,
    )[0]
    headers = latest.get("headers", {})
    subject = headers.get("Subject", "")
    body = latest.get("body", "") or ""

    combined_text = f"{subject}\n\n{body}"
    intent = guess_intent(combined_text)
    language = guess_language(combined_text)

    # Duration: basic heuristic — look for "30 minutes" or "1 hour"
    duration_minutes = 60
    if re.search(r"\b30 ?min", combined_text.lower()):
        duration_minutes = 30
    elif re.search(r"\b45 ?min", combined_text.lower()):
        duration_minutes = 45

    # Very lightweight requested_time_windows: capture common phrases only as text.
    requested_phrases: List[Dict[str, object]] = []
    for phrase in [
        "tomorrow morning",
        "tomorrow afternoon",
        "next week",
        "next monday",
        "next tuesday",
        "this week",
    ]:
        if phrase in combined_text.lower():
            requested_phrases.append({"text": phrase, "confidence": 0.6})

    participants = extract_participants(messages)
    summary = build_summary(subject, body)

    return {
        "threadId": thread_id,
        "intent": intent,
        "requested_time_windows": requested_phrases,
        "participants": participants,
        "duration_minutes": duration_minutes,
        "language": language,
        "summary": summary,
    }


def process_threads(threads_dir: Path, analysis_dir: Path, thread_id: Optional[str] = None) -> None:
    analysis_dir.mkdir(parents=True, exist_ok=True)
    if thread_id:
        paths = [threads_dir / f"{thread_id}.json"]
    else:
        paths = sorted(threads_dir.glob("*.json"))

    for path in paths:
        if not path.exists():
            continue
        thread_doc = read_thread(path)
        result = analyse_thread(thread_doc)
        out_path = analysis_dir / f"{result['threadId']}.json"
        write_json_atomic(out_path, result)
        print(f"Wrote {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse Gmail thread snapshots for booking intent and details."
    )
    parser.add_argument(
        "--threads-dir",
        default=os.path.join(".tmp", "email_threads"),
        help="Directory containing thread JSON files.",
    )
    parser.add_argument(
        "--analysis-dir",
        default=os.path.join(".tmp", "email_analysis"),
        help="Output directory for analysis JSON files.",
    )
    parser.add_argument(
        "--thread-id",
        help="Optional Gmail threadId to analyse (default: all in threads-dir).",
    )
    args = parser.parse_args()

    threads_dir = Path(args.threads_dir)
    if not threads_dir.exists():
        raise SystemExit(f"Threads dir not found: {threads_dir}")

    process_threads(threads_dir=threads_dir, analysis_dir=Path(args.analysis_dir), thread_id=args.thread_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

