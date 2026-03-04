"""
Hash PII (email, tel, mobile, address) for use across all processes.
Uses SHA-256 with optional salt from PII_HASH_SALT in .env.
Normalization matches common expectations (e.g. Meta EMAIL_SHA256 / PHONE_SHA256 when no salt).
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent


def _load_salt() -> Optional[str]:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    return (os.getenv("PII_HASH_SALT") or "").strip() or None


def normalize_email(value: str) -> str:
    """Strip and lowercase. Empty input returns ''."""
    return (value or "").strip().lower()


def normalize_phone(value: str) -> str:
    """Digits only (for tel/mobile/phone). Empty input returns ''."""
    return "".join(c for c in (value or "").strip() if c.isdigit())


def normalize_address(value: str) -> str:
    """Strip, lowercase, collapse whitespace. Empty input returns ''."""
    if not value:
        return ""
    return " ".join((value or "").strip().lower().split())


def _sha256_hex(text: str, salt: Optional[str] = None) -> str:
    data = (salt + text) if salt else text
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_email(value: str, salt: Optional[str] = None) -> str:
    """Normalize then SHA-256 hex. Empty input returns '' (no hash)."""
    n = normalize_email(value)
    return _sha256_hex(n, salt) if n else ""


def hash_phone(value: str, salt: Optional[str] = None) -> str:
    """Normalize (digits only) then SHA-256 hex. Empty input returns ''."""
    n = normalize_phone(value)
    return _sha256_hex(n, salt) if n else ""


def hash_address(value: str, salt: Optional[str] = None) -> str:
    """Normalize then SHA-256 hex. Empty input returns ''."""
    n = normalize_address(value)
    return _sha256_hex(n, salt) if n else ""


# Keys that we treat as PII and hash. Maps key -> (normalizer, hasher).
_PII_FIELDS: Dict[str, tuple] = {
    "email": (normalize_email, hash_email),
    "e-mail": (normalize_email, hash_email),
    "mail": (normalize_email, hash_email),
    "tel": (normalize_phone, hash_phone),
    "phone": (normalize_phone, hash_phone),
    "mobile": (normalize_phone, hash_phone),
    "telephone": (normalize_phone, hash_phone),
    "address": (normalize_address, hash_address),
    "street": (normalize_address, hash_address),
    "billing_address": (normalize_address, hash_address),
    "shipping_address": (normalize_address, hash_address),
}


def hash_record(
    record: Dict[str, Any],
    pii_keys: Optional[Iterable[str]] = None,
    salt: Optional[str] = None,
    in_place: bool = False,
) -> Dict[str, Any]:
    """
    Hash all known PII fields in record. Keys are matched case-insensitively.
    pii_keys: if set, only these keys are hashed; otherwise all keys that match _PII_FIELDS.
    in_place: if True, mutate record and return it; else return a shallow copy with hashed values.
    """
    if salt is None:
        salt = _load_salt()
    keys_to_hash = set((pii_keys or _PII_FIELDS.keys()))
    key_lower_to_canonical: Dict[str, str] = {k.lower(): k for k in _PII_FIELDS}
    out = record if in_place else dict(record)
    for k, v in list(record.items()):
        if not isinstance(v, str):
            continue
        k_lower = k.lower()
        canonical = key_lower_to_canonical.get(k_lower)
        if canonical is None or k_lower not in {x.lower() for x in keys_to_hash}:
            continue
        _, hasher = _PII_FIELDS[canonical]
        hashed = hasher(v, salt)
        if hashed:
            out[k] = hashed
    return out


def hash_records(
    records: Iterable[Dict[str, Any]],
    pii_keys: Optional[Iterable[str]] = None,
    salt: Optional[str] = None,
    in_place: bool = False,
) -> List[Dict[str, Any]]:
    """Hash PII in each record. Returns list of (possibly mutated) records."""
    return [hash_record(r, pii_keys=pii_keys, salt=salt, in_place=in_place) for r in records]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Hash email, tel, mobile, address (and variants) in CSV or JSON. Reads from file or stdin."
    )
    ap.add_argument("input", nargs="?", default="-", help="Input CSV or JSON file (default: stdin)")
    ap.add_argument("-o", "--output", default="-", help="Output file (default: stdout)")
    ap.add_argument("--format", choices=["csv", "json"], default=None, help="Force format (default: infer from extension or stdin)")
    ap.add_argument("--no-salt", action="store_true", help="Do not use PII_HASH_SALT (e.g. for Meta EMAIL_SHA256 compatibility)")
    ap.add_argument("--columns", nargs="*", help="Only hash these column names (default: all known PII columns)")
    args = ap.parse_args()

    salt = None if args.no_salt else _load_salt()
    infile = sys.stdin if args.input == "-" else open(args.input, newline="", encoding="utf-8-sig", errors="replace")
    outfile = sys.stdout if args.output == "-" else open(args.output, "w", newline="", encoding="utf-8")

    try:
        fmt = args.format
        if not fmt and args.input != "-":
            fmt = "json" if args.input.lower().endswith(".json") else "csv"
        if not fmt:
            fmt = "csv"

        if fmt == "csv":
            reader = csv.DictReader(infile)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
            hashed = hash_records(rows, pii_keys=args.columns or None, salt=salt, in_place=True)
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(hashed)
        else:
            data = json.load(infile)
            if isinstance(data, list):
                hash_records(data, pii_keys=args.columns or None, salt=salt, in_place=True)
            else:
                hash_record(data, pii_keys=args.columns or None, salt=salt, in_place=True)
            json.dump(data, outfile, indent=2, ensure_ascii=False)
    finally:
        if infile is not sys.stdin:
            infile.close()
        if outfile is not sys.stdout:
            outfile.close()


if __name__ == "__main__":
    main()
