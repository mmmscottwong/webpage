"""
Meta Marketing API – create and manage Custom Audiences (customer file).
Uses META_SYSTEM_USER_TOKEN and META_AD_ACCOUNT_ID from .env.
Token must have ads_management (and often business_management) scope.
See workflows/meta_audience_create.md.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GRAPH_VERSION = os.getenv("META_GRAPH_API_VERSION", "v19.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
BATCH_SIZE = 10_000  # Meta limit per request


def _get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Set {name} in .env. See workflows/meta_audience_create.md.")
    return value


def _graph_get(path: str, params: Optional[dict] = None) -> dict:
    token = _get_env("META_SYSTEM_USER_TOKEN")
    url = f"{GRAPH_BASE}{path}"
    p = {"access_token": token}
    if params:
        p.update(params)
    resp = requests.get(url, params=p, timeout=60)
    return _parse_response(resp, path)


def _graph_post(path: str, data: Optional[dict] = None, form: Optional[dict] = None) -> dict:
    token = _get_env("META_SYSTEM_USER_TOKEN")
    url = f"{GRAPH_BASE}{path}"
    if form is not None:
        form = dict(form) if form else {}
        form.setdefault("access_token", token)
        resp = requests.post(url, data=form, timeout=120)
    else:
        params = {"access_token": token}
        resp = requests.post(url, params=params, json=data or {}, timeout=120)
    return _parse_response(resp, path)


def _parse_response(resp: requests.Response, context: str) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise SystemExit(f"Meta API error {resp.status_code}: {resp.text[:500]}")
    if resp.status_code != 200:
        err = data.get("error", {})
        msg = err.get("message", json.dumps(data, ensure_ascii=False))[:400]
        raise SystemExit(f"Meta API error {resp.status_code}: {msg}")
    return data


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_phone(value: str) -> str:
    return "".join(c for c in value.strip() if c.isdigit())


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_csv_column(path: Path, column: str) -> List[str]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and column not in reader.fieldnames:
            raise SystemExit(
                f"Column '{column}' not found in CSV. Available: {list(reader.fieldnames)}"
            )
        return [row[column].strip() for row in reader if row.get(column, "").strip()]


def create_custom_audience(
    name: str,
    description: Optional[str] = None,
) -> str:
    ad_account_id = _get_env("META_AD_ACCOUNT_ID")
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"
    path = f"/{ad_account_id}/customaudiences"
    form = {
        "name": name,
        "subtype": "CUSTOM",
        "customer_file_source": "USER_PROVIDED_ONLY",
    }
    if description:
        form["description"] = description
    data = _graph_post(path, form=form)
    audience_id = data.get("id")
    if not audience_id:
        raise SystemExit(f"Create response missing id: {data}")
    return audience_id


def add_users_to_audience(
    audience_id: str,
    schema: str,
    hashed_values: List[str],
    session_id: Optional[int] = None,
    batch_seq: int = 1,
    last_batch: bool = True,
    estimated_total: Optional[int] = None,
) -> dict:
    payload = {
        "schema": schema,
        "data": [[h] for h in hashed_values],
    }
    form = {"payload": json.dumps(payload)}
    if session_id is not None:
        session = {
            "session_id": session_id,
            "batch_seq": batch_seq,
            "last_batch_flag": last_batch,
        }
        if estimated_total is not None:
            session["estimated_num_total"] = estimated_total
        form["session"] = json.dumps(session)
    return _graph_post(f"/{audience_id}/users", form=form)


def update_audience_name(audience_id: str, name: str) -> dict:
    """Update custom audience name via POST to /{audience_id}."""
    return _graph_post(f"/{audience_id}", form={"name": name})


def cmd_list(args: argparse.Namespace) -> None:
    ad_account_id = _get_env("META_AD_ACCOUNT_ID")
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"
    data = _graph_get(f"/{ad_account_id}/customaudiences", {"fields": "id,name,subtype,approximate_count"})
    print("id\tname\tsubtype\tapproximate_count")
    for item in data.get("data", []):
        print(f"{item.get('id', '')}\t{item.get('name', '')}\t{item.get('subtype', '')}\t{item.get('approximate_count', '')}")


def cmd_create(args: argparse.Namespace) -> None:
    name = args.name or "Custom Audience"
    description = getattr(args, "description", None) or ""
    audience_id = create_custom_audience(name=name, description=description or None)
    print(f"Created custom audience: {audience_id}")
    if args.csv and args.email_column:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise SystemExit(f"CSV not found: {csv_path}")
        raw_values = _read_csv_column(csv_path, args.email_column)
        if not raw_values:
            raise SystemExit("No non-empty values in the chosen column.")
        normalized = [_normalize_email(v) for v in raw_values if v]
        normalized = list(dict.fromkeys(normalized))
        hashed = [_sha256_hex(v) for v in normalized]
        total = len(hashed)
        session_id = hash(audience_id) % (2**31)
        offset = 0
        batch_num = 0
        while offset < total:
            chunk = hashed[offset : offset + BATCH_SIZE]
            batch_num += 1
            last = offset + len(chunk) >= total
            add_users_to_audience(
                audience_id,
                schema="EMAIL_SHA256",
                hashed_values=chunk,
                session_id=session_id,
                batch_seq=batch_num,
                last_batch=last,
                estimated_total=total,
            )
            offset += len(chunk)
        print(f"Uploaded {total} hashed emails in {batch_num} batch(es). Audience ID: {audience_id}")
    else:
        print(f"Audience ID: {audience_id}")


def cmd_add_users(args: argparse.Namespace) -> None:
    """Upload hashed emails from CSV to an existing custom audience."""
    audience_id = args.audience_id.strip()
    if not audience_id:
        raise SystemExit("--audience-id is required.")
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    raw_values = _read_csv_column(csv_path, args.email_column)
    if not raw_values:
        raise SystemExit("No non-empty values in the chosen column.")
    normalized = [_normalize_email(v) for v in raw_values if v]
    normalized = list(dict.fromkeys(normalized))
    hashed = [_sha256_hex(v) for v in normalized]
    total = len(hashed)
    session_id = hash(audience_id) % (2**31)
    offset = 0
    batch_num = 0
    while offset < total:
        chunk = hashed[offset : offset + BATCH_SIZE]
        batch_num += 1
        last = offset + len(chunk) >= total
        add_users_to_audience(
            audience_id,
            schema="EMAIL_SHA256",
            hashed_values=chunk,
            session_id=session_id,
            batch_seq=batch_num,
            last_batch=last,
            estimated_total=total,
        )
        offset += len(chunk)
    print(f"Uploaded {total} hashed emails to audience {audience_id} in {batch_num} batch(es).")


def cmd_rename(args: argparse.Namespace) -> None:
    """Rename an existing custom audience."""
    audience_id = args.audience_id.strip()
    name = args.name.strip()
    if not audience_id or not name:
        raise SystemExit("--audience-id and --name are required.")
    update_audience_name(audience_id, name)
    print(f"Renamed audience {audience_id} to: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Meta Marketing API – Custom Audiences (create, list, add users from CSV)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="List custom audiences for the ad account")
    list_parser.set_defaults(func=cmd_list)
    create_parser = sub.add_parser("create", help="Create a custom audience (optionally from CSV)")
    create_parser.add_argument("--name", "-n", help="Audience name")
    create_parser.add_argument("--description", "-d", help="Audience description")
    create_parser.add_argument("--csv", "-c", help="Path to CSV file with email/phone column")
    create_parser.add_argument(
        "--email-column",
        "-e",
        default="email",
        help="CSV column name for emails (default: email)",
    )
    create_parser.set_defaults(func=cmd_create)
    add_parser = sub.add_parser("add-users", help="Upload emails from CSV to an existing audience")
    add_parser.add_argument("--audience-id", "-a", required=True, help="Custom audience ID (numeric)")
    add_parser.add_argument("--csv", "-c", required=True, help="Path to CSV with email column")
    add_parser.add_argument("--email-column", "-e", default="email", help="CSV column name (default: email)")
    add_parser.set_defaults(func=cmd_add_users)
    rename_parser = sub.add_parser("rename", help="Rename an existing custom audience")
    rename_parser.add_argument("--audience-id", "-a", required=True, help="Custom audience ID (numeric)")
    rename_parser.add_argument("--name", "-n", required=True, help="New audience name")
    rename_parser.set_defaults(func=cmd_rename)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
