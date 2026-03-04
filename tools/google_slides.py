"""
Google Slides API – list presentations and read/write slides.
Uses shared credentials from google_auth (run google_auth.py once).
"""
import argparse
import sys
from pathlib import Path

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from tools.google_auth import get_credentials, run_oauth_flow


def get_slides_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("slides", "v1", credentials=creds)


def get_presentation(service, presentation_id):
    """Get presentation metadata and slide IDs."""
    return service.presentations().get(presentationId=presentation_id).execute()


def list_slides(service, presentation_id):
    """Return slide IDs and titles (from title shapes if present)."""
    pres = get_presentation(service, presentation_id)
    slides = pres.get("slides", [])
    result = []
    for i, s in enumerate(slides):
        slide_id = s.get("objectId", "")
        # Try to get title from first text shape
        title = ""
        for elem in s.get("pageElements", []):
            if "shape" in elem and "text" in elem["shape"].get("text", {}).get("textElements", []):
                for te in elem["shape"]["text"]["textElements"]:
                    if "textRun" in te:
                        title = te["textRun"].get("content", "").strip() or title
                        break
                if title:
                    break
        result.append({"index": i + 1, "id": slide_id, "title": title or "(no title)"})
    return result


def main():
    parser = argparse.ArgumentParser(description="Google Slides – list slides in a presentation")
    parser.add_argument("--list", action="store_true", help="List slides")
    parser.add_argument("--presentation-id", required=True, help="Presentation ID (from URL)")
    args = parser.parse_args()

    if not args.list:
        parser.print_help()
        return 0

    service = get_slides_service()
    for s in list_slides(service, args.presentation_id):
        print(s["index"], s["id"], s["title"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
