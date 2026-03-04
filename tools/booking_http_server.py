"""
Minimal HTTP server exposing /bookings/email for n8n to call.

Usage (from project root):
    py tools/booking_http_server.py --host 0.0.0.0 --port 8080

Environment:
- BOOKING_AGENT_SECRET: shared secret. Requests must send header X-AGENT-TOKEN with this value.
- BOOKING_AGENT_EMAIL: your own email address (used when drafting replies).

Endpoint:
- POST /bookings/email
  Body JSON:
    {
      "threadId": "...",        # required
      "messageId": "...",       # optional, not used by tools yet
      "from": "...",            # optional
      "to": "...",              # optional
      "subject": "...",         # optional
      "snippet": "..."          # optional
    }

Behaviour:
- Validates secret header.
- Runs the booking tool chain for the given threadId:
  - gmail_fetch_threads.py --thread-id <threadId>
  - analyze_email_for_booking.py --thread-id <threadId>
  - thread_state_manager.py --update-only
  - google_calendar_availability.py
  - generate_time_proposals.py --thread-id <threadId>
  - draft_booking_email_reply.py --thread-id <threadId> --my-email <BOOKING_AGENT_EMAIL>
- Returns a short JSON response { "ok": true, "threadId": "...", "steps": [...] }.
"""
import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(args: List[str]) -> Tuple[bool, str]:
    """Run a single subprocess step from the project root."""
    try:
        completed = subprocess.run(
            [sys.executable] + args,
            cwd=str(PROJECT_ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        return True, completed.stdout.strip()
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return False, output.strip()


class BookingHandler(BaseHTTPRequestHandler):
    server_version = "BookingHTTP/1.0"

    def _send_json(self, code: int, payload: Dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # type: ignore[override]
        if self.path == "/health":
            self._send_json(200, {"ok": True})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # type: ignore[override]
        if self.path != "/bookings/email":
            self._send_json(404, {"error": "Not found"})
            return

        secret = os.getenv("BOOKING_AGENT_SECRET")
        if secret:
            token = self.headers.get("X-AGENT-TOKEN")
            if not token or token != secret:
                self._send_json(401, {"error": "Unauthorized"})
                return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        thread_id = body.get("threadId")
        if not thread_id:
            self._send_json(400, {"error": "threadId is required"})
            return

        my_email = os.getenv("BOOKING_AGENT_EMAIL") or None

        steps_run: List[str] = []
        errors: List[str] = []

        def step(label: str, args: List[str]) -> bool:
            ok, output = run_step(args)
            if ok:
                steps_run.append(label)
            else:
                errors.append(f"{label} failed: {output}")
            return ok

        # 1) Fetch the specific thread
        if not step(
            "gmail_fetch_threads",
            ["tools/gmail_fetch_threads.py", "--thread-id", thread_id],
        ):
            self._send_json(
                500,
                {"ok": False, "threadId": thread_id, "steps": steps_run, "errors": errors},
            )
            return

        # 2) Analyse intent/details for this thread
        step(
            "analyze_email_for_booking",
            ["tools/analyze_email_for_booking.py", "--thread-id", thread_id],
        )

        # 3) Update thread state
        step(
            "thread_state_manager",
            ["tools/thread_state_manager.py", "--update-only"],
        )

        # 4) Refresh calendar availability
        step(
            "google_calendar_availability",
            ["tools/google_calendar_availability.py"],
        )

        # 5) Generate proposals for this thread
        step(
            "generate_time_proposals",
            ["tools/generate_time_proposals.py", "--thread-id", thread_id],
        )

        # 6) Draft reply using templates
        draft_args = ["tools/draft_booking_email_reply.py", "--thread-id", thread_id]
        if my_email:
            draft_args.extend(["--my-email", my_email])
        step("draft_booking_email_reply", draft_args)

        status_code = 200 if not errors else 500
        self._send_json(
            status_code,
            {
                "ok": not errors,
                "threadId": thread_id,
                "steps": steps_run,
                "errors": errors,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal HTTP server exposing /bookings/email for n8n."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Listen host (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8080, help="Listen port (default 8080).")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), BookingHandler)
    print(f"Booking HTTP server listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

