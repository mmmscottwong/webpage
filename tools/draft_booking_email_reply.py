"""
Draft booking-related email replies based on thread, analysis, state, and proposals.

Inputs:
- Thread snapshot: .tmp/email_threads/{thread_id}.json
- Analysis: .tmp/email_analysis/{thread_id}.json
- State: .tmp/thread_state/{thread_id}.json
- Proposals: .tmp/time_proposals/{thread_id}.json

Outputs:
- Draft JSON at .tmp/email_drafts/{thread_id}_{last_message_id}.json:
  {
    "threadId": "...",
    "messageId": "...",           # last message in the thread
    "to": "client@example.com",
    "subject": "Re: Original subject",
    "body_text": "...",
    "body_html": "...",
    "intent": "booking_new" | "reschedule" | "cancel",
    "language": "en"
  }

This version uses simple templates instead of an external LLM so it works
out-of-the-box. You can later replace the template generation with a call to
your preferred LLM while preserving the same JSON interface.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def latest_message(thread_doc: Dict) -> Dict:
    messages = thread_doc.get("messages", [])
    if not messages:
        return {}
    return sorted(messages, key=lambda m: int(m.get("internalDate") or 0), reverse=True)[0]


def pick_client_email(participants: List[Dict], my_email: Optional[str] = None) -> Optional[str]:
    if not participants:
        return None
    if my_email:
        for p in participants:
            if p.get("email") and p["email"].lower() != my_email.lower():
                return p["email"]
    return participants[0].get("email")


def format_slot_range(start_iso: str, end_iso: str) -> str:
    from datetime import datetime

    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except Exception:
        return f"{start_iso} – {end_iso}"

    date_str = start.strftime("%Y-%m-%d")
    start_time = start.strftime("%H:%M")
    end_time = end.strftime("%H:%M")
    return f"{date_str} {start_time}–{end_time}"


def build_body_for_intent(intent: str, proposals: List[Dict], language: str) -> str:
    slots_lines = [f"- {format_slot_range(s['start'], s['end'])}" for s in proposals] or [
        "- (no concrete slots generated yet)"
    ]
    slots_text = "\n".join(slots_lines)

    if intent == "cancel":
        return (
            "Thank you for letting us know.\n\n"
            "Your booking has been cancelled as requested. If you would like to "
            "schedule a new time, just reply to this email and we will be happy to arrange it.\n"
        )
    if intent == "reschedule":
        return (
            "Thanks for your message about rescheduling.\n\n"
            "Here are some alternative time slots we can offer:\n"
            f"{slots_text}\n\n"
            "Please reply with the option that works best for you, or suggest another time "
            "and we'll do our best to accommodate."
        )

    return (
        "Thank you for your interest in booking with us.\n\n"
        "Here are some available time slots:\n"
        f"{slots_text}\n\n"
        "Please reply with your preferred option, and we will confirm the appointment "
        "and send a calendar invite."
    )


def draft_reply(
    thread_doc: Dict,
    analysis: Dict,
    state: Dict,
    proposals: Dict,
    my_email: Optional[str] = None,
) -> Dict:
    latest = latest_message(thread_doc)
    headers = latest.get("headers", {})
    subject = headers.get("Subject", "(no subject)")
    thread_id = thread_doc.get("threadId")
    message_id = latest.get("id")

    participants = analysis.get("participants") or []
    to_email = pick_client_email(participants, my_email=my_email)

    intent = analysis.get("intent", "booking_new")
    language = analysis.get("language", "en")
    proposed_slots = proposals.get("proposed_slots", [])

    body_text = build_body_for_intent(intent=intent, proposals=proposed_slots, language=language)
    body_html = body_text.replace("\n", "<br />\n")

    return {
        "threadId": thread_id,
        "messageId": message_id,
        "to": to_email,
        "subject": f"Re: {subject}",
        "body_text": body_text,
        "body_html": body_html,
        "intent": intent,
        "language": language,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draft a booking-related email reply using templates."
    )
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Gmail threadId to draft a reply for.",
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
        help="Directory containing state JSON.",
    )
    parser.add_argument(
        "--proposals-dir",
        default=os.path.join(".tmp", "time_proposals"),
        help="Directory containing time proposals JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(".tmp", "email_drafts"),
        help="Output directory for draft JSON.",
    )
    parser.add_argument(
        "--my-email",
        default=None,
        help="Your own email address (used to identify the client in participants).",
    )
    args = parser.parse_args()

    thread_path = Path(args.threads_dir) / f"{args.thread_id}.json"
    analysis_path = Path(args.analysis_dir) / f"{args.thread_id}.json"
    state_path = Path(args.state_dir) / f"{args.thread_id}.json"
    proposals_path = Path(args.proposals_dir) / f"{args.thread_id}.json"

    if not thread_path.exists():
        raise SystemExit(f"Thread snapshot not found: {thread_path}")
    if not analysis_path.exists():
        raise SystemExit(f"Analysis not found: {analysis_path}")
    if not state_path.exists():
        raise SystemExit(f"State not found: {state_path}")
    if not proposals_path.exists():
        raise SystemExit(f"Proposals not found: {proposals_path}")

    thread_doc = read_json(thread_path)
    analysis = read_json(analysis_path)
    state = read_json(state_path)
    proposals = read_json(proposals_path)

    draft = draft_reply(thread_doc, analysis, state, proposals, my_email=args.my_email)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    message_id = draft.get("messageId") or "latest"
    out_path = out_dir / f"{args.thread_id}_{message_id}.json"
    write_json_atomic(out_path, draft)

    print(json.dumps(draft, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

