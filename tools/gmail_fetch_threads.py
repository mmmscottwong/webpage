"""
Fetch Gmail threads matching a search query and write per-thread JSON snapshots.

Outputs one JSON file per thread to .tmp/email_threads/{thread_id}.json with:
{
  "threadId": "...",
  "historyId": "...",
  "messages": [
    {
      "id": "...",
      "threadId": "...",
      "internalDate": "ms since epoch as string",
      "headers": { "From": "...", "To": "...", "Subject": "...", ... },
      "snippet": "...",
      "body": "plain text body (best-effort)"
    }
  ]
}
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.google_auth import get_credentials, run_oauth_flow  # type: ignore
from tools.google_gmail import decode_body  # type: ignore


def get_gmail_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def headers_to_dict(payload_headers: List[Dict[str, str]]) -> Dict[str, str]:
    return {h.get("name", ""): h.get("value", "") for h in payload_headers if h.get("name")}


def write_json_atomic(path: Path, data: Dict) -> None:
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def fetch_one_thread(service, thread_id: str, output_dir: Path, user_id: str = "me") -> None:
    """Fetch a single Gmail thread by ID and write its snapshot."""
    ensure_dir(output_dir)
    full = (
        service.users()
        .threads()
        .get(userId=user_id, id=thread_id, format="full")
        .execute()
    )
    messages_out = []
    for m in full.get("messages", []):
        payload = m.get("payload", {}) or {}
        headers = headers_to_dict(payload.get("headers", []))
        body_text = decode_body(payload)
        messages_out.append(
            {
                "id": m.get("id"),
                "threadId": m.get("threadId"),
                "internalDate": m.get("internalDate"),
                "snippet": m.get("snippet", ""),
                "headers": headers,
                "body": body_text,
            }
        )

    thread_id = full.get("id", thread_id)
    doc = {
        "threadId": thread_id,
        "historyId": full.get("historyId"),
        "messages": messages_out,
    }
    out_path = output_dir / f"{thread_id}.json"
    write_json_atomic(out_path, doc)
    print(f"Wrote {out_path}")


def fetch_threads(
    service,
    query: str,
    max_threads: int,
    output_dir: Path,
    user_id: str = "me",
) -> None:
    """Fetch multiple threads using a Gmail search query."""
    ensure_dir(output_dir)

    list_kwargs = {"userId": user_id, "maxResults": max_threads}
    if query:
        list_kwargs["q"] = query
    result = service.users().threads().list(**list_kwargs).execute()
    threads = result.get("threads", [])

    for t in threads:
        fetch_one_thread(service, t["id"], output_dir, user_id=user_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Gmail threads and write per-thread JSON snapshots."
    )
    parser.add_argument(
        "--query",
        "-q",
        default="",
        help='Gmail search query, e.g. \'is:unread subject:(booking OR consultation)\'',
    )
    parser.add_argument(
        "--thread-id",
        help="Optional Gmail threadId to fetch a single specific thread.",
    )
    parser.add_argument(
        "--max-threads",
        "-n",
        type=int,
        default=20,
        help="Maximum number of threads to fetch.",
    )
    parser.add_argument(
        "--threads-dir",
        default=os.path.join(".tmp", "email_threads"),
        help="Output directory for thread JSON snapshots.",
    )
    parser.add_argument(
        "--user-id",
        default="me",
        help="Gmail userId (default 'me').",
    )
    args = parser.parse_args()

    service = get_gmail_service()
    if args.thread_id:
        fetch_one_thread(
            service=service,
            thread_id=args.thread_id,
            output_dir=Path(args.threads_dir),
            user_id=args.user_id,
        )
    else:
        fetch_threads(
            service=service,
            query=args.query,
            max_threads=args.max_threads,
            output_dir=Path(args.threads_dir),
            user_id=args.user_id,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

