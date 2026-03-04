"""
WordPress REST API – site info, posts, pages.
Uses Application Password from .env (WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD).
See workflows/wordpress_setup.md.
"""
import argparse
import base64
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

WORDPRESS_URL = None
WORDPRESS_USER = None
WORDPRESS_APP_PASSWORD = None


def _load_config():
    global WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD
    import os
    WORDPRESS_URL = (os.getenv("WORDPRESS_URL") or "").rstrip("/")
    WORDPRESS_USER = os.getenv("WORDPRESS_USER") or ""
    WORDPRESS_APP_PASSWORD = (os.getenv("WORDPRESS_APP_PASSWORD") or "").replace(" ", "")
    return WORDPRESS_URL and WORDPRESS_USER and WORDPRESS_APP_PASSWORD


def _auth_headers():
    if not _load_config():
        raise SystemExit(
            "Set WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD in .env. See workflows/wordpress_setup.md."
        )
    token = base64.b64encode(f"{WORDPRESS_USER}:{WORDPRESS_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def get_site_info():
    """Fetch site name and URL from WP REST API root."""
    r = requests.get(f"{WORDPRESS_URL}/wp-json/", headers=_auth_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    return {"name": data.get("name", "?"), "url": data.get("url", WORDPRESS_URL or "?")}


def get_posts(per_page=10, page=1, status="publish"):
    """Fetch posts."""
    r = requests.get(
        f"{WORDPRESS_URL}/wp-json/wp/v2/posts",
        headers=_auth_headers(),
        params={"per_page": per_page, "page": page, "status": status},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_pages(per_page=10, page=1, status="publish"):
    """Fetch pages."""
    r = requests.get(
        f"{WORDPRESS_URL}/wp-json/wp/v2/pages",
        headers=_auth_headers(),
        params={"per_page": per_page, "page": page, "status": status},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="WordPress REST API – site info, posts, pages")
    parser.add_argument("--site-info", action="store_true", help="Print site name and URL")
    parser.add_argument("--posts", action="store_true", help="List recent posts")
    parser.add_argument("--pages", action="store_true", help="List recent pages")
    parser.add_argument("-n", "--per-page", type=int, default=10, help="Number of items (posts/pages)")
    args = parser.parse_args()

    if not args.site_info and not args.posts and not args.pages:
        parser.print_help()
        return 0

    _load_config()
    headers = _auth_headers()

    if args.site_info:
        info = get_site_info()
        name = info.get("name", "?")
        url = info.get("url", "?")
        print("Site:", name)
        print("URL:", url)

    if args.posts:
        for p in get_posts(per_page=args.per_page):
            print(p.get("id"), p.get("date", "")[:10], p.get("title", {}).get("rendered", "?")[:60])

    if args.pages:
        for p in get_pages(per_page=args.per_page):
            print(p.get("id"), p.get("date", "")[:10], p.get("title", {}).get("rendered", "?")[:60])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
