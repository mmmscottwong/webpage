"""
Gmail API – list, read, and send messages (with optional attachment).
Uses shared credentials from google_auth (run google_auth.py once).
"""
import argparse
import base64
import sys
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from tools.google_auth import get_credentials, run_oauth_flow


def get_gmail_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def list_messages(service, user_id="me", max_results=10, query=None):
    """List message IDs (and optionally fetch snippets)."""
    params = {"userId": user_id, "maxResults": max_results}
    if query:
        params["q"] = query
    result = service.users().messages().list(**params).execute()
    return result.get("messages", [])


def get_message(service, msg_id, user_id="me"):
    """Get a single message by ID."""
    return service.users().messages().get(userId=user_id, id=msg_id).execute()


def decode_body(payload):
    """Extract plain text body from message payload."""
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    return ""


def send_email(to, subject, body_text, attachment_path=None, user_id="me"):
    """
    Send an email via Gmail API. Optionally attach a file.
    to: comma-separated or single email address.
    Returns the sent message dict.
    """
    service = get_gmail_service()
    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if attachment_path:
        path = Path(attachment_path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {path}")
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(userId=user_id, body={"raw": raw}).execute()


def main():
    parser = argparse.ArgumentParser(description="Gmail – list, show, or send messages")
    parser.add_argument("--list", action="store_true", help="List recent messages")
    parser.add_argument("--query", "-q", help="Gmail search query (e.g. is:unread)")
    parser.add_argument("-n", "--max-results", type=int, default=10, help="Max messages to list")
    parser.add_argument("--show", metavar="MSG_ID", help="Show one message by ID")
    parser.add_argument("--send", action="store_true", help="Send an email")
    parser.add_argument("--to", dest="to_addr", metavar="EMAIL", help="Recipient (for --send)")
    parser.add_argument("--subject", help="Subject (for --send)")
    parser.add_argument("--body", default="", help="Body text (for --send)")
    parser.add_argument("--attach", metavar="FILE", help="Attachment path (for --send)")
    args = parser.parse_args()

    if not args.list and not args.show and not args.send:
        parser.print_help()
        return 0

    service = get_gmail_service()
    if args.list:
        for msg in list_messages(service, max_results=args.max_results, query=args.query):
            m = get_message(service, msg["id"])
            headers = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")
            snippet = m.get("snippet", "")[:60]
            print(msg["id"], subject or snippet)
    if args.show:
        m = get_message(service, args.show)
        headers = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
        print("From:", headers.get("From"))
        print("Subject:", headers.get("Subject"))
        print("Date:", headers.get("Date"))
        print("---")
        print(decode_body(m.get("payload", {})))

    if args.send:
        if not args.to_addr or not args.subject:
            print("Error: --send requires --to and --subject.", file=sys.stderr)
            return 1
        sent = send_email(
            to=args.to_addr,
            subject=args.subject,
            body_text=args.body or "",
            attachment_path=args.attach,
        )
        print("Sent. Message ID:", sent.get("id"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
