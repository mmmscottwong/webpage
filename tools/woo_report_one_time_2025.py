"""
Report: customers who bought online exactly once in 2025 and never bought again.

Data source: WooCommerce orders via tools/woocommerce_api.py.
Output: .tmp/woo_one_time_customers_2025.csv

Run from project root:
    py tools/woo_report_one_time_2025.py
"""
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.woocommerce_api import _orders_in_range  # type: ignore


def load_all_orders():
    """
    Load all orders in a wide date range (UTC) with completed/processing status.
    Adjust the from/to years if your store has a longer history.
    """
    start = datetime(2015, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return _orders_in_range(start.isoformat(), end.isoformat(), statuses=["completed", "processing"])


def build_one_time_2025_customers(orders):
    """
    Group orders by billing email.
    Select customers with exactly 1 order and that order is in 2025 (UTC date_created year).
    """
    by_email = {}
    for o in orders:
        billing = o.get("billing") or {}
        email = (billing.get("email") or "").strip()
        if not email:
            continue
        created = o.get("date_created")
        if not created:
            continue
        try:
            # WooCommerce date_created is ISO 8601 with timezone; parse to datetime
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            continue
        key = email.lower()
        entry = by_email.get(key)
        total = float(o.get("total", 0) or 0)
        if entry is None:
            by_email[key] = {
                "email": email,
                "first_name": billing.get("first_name") or "",
                "last_name": billing.get("last_name") or "",
                "order_count": 1,
                "first_order_id": o.get("id"),
                "first_order_date": created,
                "last_order_date": created,
                "total_spent": total,
            }
        else:
            entry["order_count"] += 1
            # update first/last order dates
            if created < entry["first_order_date"]:
                entry["first_order_date"] = created
                entry["first_order_id"] = o.get("id")
            if created > entry["last_order_date"]:
                entry["last_order_date"] = created
            entry["total_spent"] += total

    # Filter: exactly one order, and that order in 2025
    out = []
    for entry in by_email.values():
        if entry["order_count"] != 1:
            continue
        try:
            dt = datetime.fromisoformat(entry["first_order_date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year == 2025:
            out.append(entry)
    return out


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "email",
                "first_name",
                "last_name",
                "first_order_id",
                "first_order_date",
                "last_order_date",
                "total_spent",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.get("email", ""),
                    r.get("first_name", ""),
                    r.get("last_name", ""),
                    r.get("first_order_id", ""),
                    r.get("first_order_date", ""),
                    r.get("last_order_date", ""),
                    f"{r.get('total_spent', 0):.2f}",
                ]
            )


def main():
    orders = load_all_orders()
    rows = build_one_time_2025_customers(orders)
    out_path = Path(__file__).resolve().parent.parent / ".tmp" / "woo_one_time_customers_2025.csv"
    write_csv(rows, out_path)
    print(f"Wrote {len(rows)} customers to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

