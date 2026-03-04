"""
Send an email message, optionally using the latest draft for a booking thread.

Two main usage patterns:
1) Explicit:
   py tools/send_gmail_message.py --to client@example.com --subject "Hi" --body "..."

2) Use latest draft for a thread:
   py tools/send_gmail_message.py --thread-id THREAD_ID --use-latest-draft
   (expects a draft JSON in .tmp/email_drafts/{thread_id}_{messageId}.json)
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.google_gmail import send_email  # type: ignore


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pick_latest_draft(drafts_dir: Path, thread_id: str) -> Optional[Path]:
    candidates = sorted(drafts_dir.glob(f"{thread_id}_*.json"))
    return candidates[-1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send an email, optionally from a booking draft.")
    parser.add_argument("--to", help="Recipient email address.")
    parser.add_argument("--subject", help="Email subject.")
    parser.add_argument("--body", default="", help="Email body text.")
    parser.add_argument(
        "--thread-id",
        help="Gmail threadId (used with --use-latest-draft).",
    )
    parser.add_argument(
        "--use-latest-draft",
        action="store_true",
        help="If set, load the latest draft JSON for the given --thread-id.",
    )
    parser.add_argument(
        "--drafts-dir",
        default=os.path.join(".tmp", "email_drafts"),
        help="Directory containing draft JSON files.",
    )
    args = parser.parse_args()

    to = args.to
    subject = args.subject
    body = args.body

    if args.use_latest_draft:
        if not args.thread_id:
            raise SystemExit("--use-latest-draft requires --thread-id")
        drafts_dir = Path(args.drafts_dir)
        draft_path = pick_latest_draft(drafts_dir, args.thread_id)
        if not draft_path:
            raise SystemExit(f"No draft found for thread {args.thread_id} in {drafts_dir}")
        draft = read_json(draft_path)
        to = draft.get("to") or to
        subject = draft.get("subject") or subject
        body = draft.get("body_text") or body

    if not to or not subject:
        parser.print_help()
        return 1

    sent = send_email(to=to, subject=subject, body_text=body or "")
    print("Sent. Message ID:", sent.get("id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

