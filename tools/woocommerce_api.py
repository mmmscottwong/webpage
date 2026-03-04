"""
WooCommerce REST API – products, orders, sales by product.
Uses consumer key/secret from .env (WORDPRESS_URL, WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET).
See workflows/wordpress_setup.md.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _load_config():
    import os
    base_url = (os.getenv("WORDPRESS_URL") or "").rstrip("/")
    key = os.getenv("WOOCOMMERCE_CONSUMER_KEY") or ""
    secret = os.getenv("WOOCOMMERCE_CONSUMER_SECRET") or ""
    return base_url, key, secret


def _api_url(path=""):
    base, key, secret = _load_config()
    if not base or not key or not secret:
        raise SystemExit(
            "Set WORDPRESS_URL, WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET in .env. See workflows/wordpress_setup.md."
        )
    return f"{base}/wp-json/wc/v3/{path.lstrip('/')}", key, secret


def _get(path, params=None):
    url, key, secret = _api_url(path)
    r = requests.get(url, auth=(key, secret), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _patch(path, data):
    """PATCH to update a resource (e.g. product)."""
    url, key, secret = _api_url(path)
    r = requests.patch(url, auth=(key, secret), json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def get_product(product_id):
    """Fetch a single product by ID."""
    return _get(f"products/{product_id}")


def get_products(per_page=10, page=1, status="publish"):
    """Fetch products."""
    return _get("products", {"per_page": per_page, "page": page, "status": status})


def update_product(product_id, **fields):
    """
    Update product by ID. Pass only fields to change, e.g.:
    update_product(123, name="New name", regular_price="99", stock_quantity=50, stock_status="instock")
    """
    return _patch(f"products/{product_id}", fields)


def get_stock(product_id):
    """Get stock_quantity and stock_status for a product. Returns (quantity or None, status)."""
    p = get_product(product_id)
    qty = p.get("stock_quantity")
    if qty is not None:
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            pass
    return qty, p.get("stock_status", "")


def set_stock(product_id, quantity, manage_stock=True):
    """Set product stock to an absolute value. Ensures manage_stock=True if changing quantity."""
    return update_product(
        product_id,
        stock_quantity=quantity,
        manage_stock=manage_stock,
        stock_status="instock" if quantity is not None and int(quantity) > 0 else "outofstock",
    )


def adjust_stock(product_id, delta):
    """Add or subtract from current stock. delta can be positive or negative. Returns new quantity."""
    qty, _ = get_stock(product_id)
    if qty is None:
        raise ValueError(f"Product {product_id} has no stock_quantity (manage_stock may be off). Fetch product to confirm.")
    new_qty = max(0, int(qty) + int(delta))
    set_stock(product_id, new_qty)
    return new_qty


def get_orders(per_page=10, page=1, status=None, after=None, before=None):
    """Fetch orders. status: any, pending, processing, on-hold, completed, cancelled, refunded, failed."""
    params = {"per_page": per_page, "page": page}
    if status:
        params["status"] = status
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    return _get("orders", params)


def get_orders_today(per_page=100, use_hk_time=True):
    """Orders created today. Default: Hong Kong (UTC+8) midnight-to-midnight; else UTC."""
    if use_hk_time:
        from datetime import timezone as tz_module
        hk = tz_module(timedelta(hours=8))
        now = datetime.now(hk)
    else:
        now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    # WooCommerce expects ISO8601; store usually stores UTC
    if use_hk_time:
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        after, before = start_utc.isoformat(), end_utc.isoformat()
    else:
        after, before = start.isoformat(), end.isoformat()
    all_orders = []
    page = 1
    while True:
        batch = get_orders(per_page=per_page, page=page, after=after, before=before)
        if not batch:
            break
        all_orders.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return all_orders


def _get_order(order_id):
    """Fetch single order (full details including line_items)."""
    url, key, secret = _api_url(f"orders/{order_id}")
    r = requests.get(url, auth=(key, secret), timeout=30)
    r.raise_for_status()
    return r.json()


def _orders_in_range(after_iso, before_iso, statuses=None):
    """Fetch all orders between after_iso and before_iso (UTC ISO8601). statuses: list e.g. ['completed','processing']."""
    all_orders = []
    page = 1
    per_page = 100
    while True:
        params = {"per_page": per_page, "page": page, "after": after_iso, "before": before_iso}
        if statuses:
            params["status"] = ",".join(statuses)
        batch = _get("orders", params)
        if not batch:
            break
        all_orders.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return all_orders


def _sum_line_items_by_product(orders, product_name_substring=None):
    """Sum quantities from orders' line_items. If product_name_substring, only count matching names (case-insensitive). Returns total qty."""
    key = (product_name_substring or "").lower()
    total_qty = 0
    for o in orders:
        if o.get("status") not in ("completed", "processing"):
            continue
        line_items = o.get("line_items")
        if not line_items:
            try:
                full = _get_order(o["id"])
                line_items = full.get("line_items", [])
            except Exception:
                line_items = []
        for item in line_items or []:
            name = (item.get("name") or "")
            if not key or key in name.lower():
                total_qty += int(item.get("quantity", 0))
    return total_qty


def purchasers_between(from_date, to_date, use_hk_time=True):
    """
    Return unique customers who made a purchase (completed or processing) between from_date and to_date (YYYY-MM-DD, inclusive).
    Returns list of dicts: {email, first_name, last_name, order_id, order_date, total}.
    """
    from datetime import timezone as tz_module

    if use_hk_time:
        hk = tz_module(timedelta(hours=8))
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=hk, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=hk, hour=23, minute=59, second=59, microsecond=999999)
    else:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)

    start_utc = start.astimezone(timezone.utc).isoformat()
    end_utc = end.astimezone(timezone.utc).isoformat()
    orders = _orders_in_range(start_utc, end_utc, statuses=["completed", "processing"])

    by_email = {}
    for o in orders:
        billing = o.get("billing") or {}
        email = (billing.get("email") or "").strip()
        if not email:
            continue
        key = email.lower()
        if key in by_email:
            continue
        by_email[key] = {
            "email": email,
            "first_name": billing.get("first_name") or "",
            "last_name": billing.get("last_name") or "",
            "order_id": o.get("id"),
            "order_date": o.get("date_created") or "",
            "total": o.get("total") or "",
        }
    return list(by_email.values())


def customers_for_product_between(from_date, to_date, sku=None, product_name_substring=None, use_hk_time=True):
    """
    Return unique customers who bought a given product between from_date and to_date (YYYY-MM-DD, inclusive).
    - Filters orders with status completed or processing.
    - Matches line_items by exact SKU when available; falls back to name substring.
    - Returns list of dicts: {email, first_name, last_name, order_id, order_date, total, product_name, quantity}.
    """
    from datetime import timezone as tz_module

    if use_hk_time:
        hk = tz_module(timedelta(hours=8))
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=hk, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=hk, hour=23, minute=59, second=59, microsecond=999999)
    else:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)

    start_utc = start.astimezone(timezone.utc).isoformat()
    end_utc = end.astimezone(timezone.utc).isoformat()
    orders = _orders_in_range(start_utc, end_utc, statuses=["completed", "processing"])

    sku_key = (sku or "").strip()
    name_key = (product_name_substring or "").lower() if product_name_substring else None

    by_email = {}
    for o in orders:
        line_items = o.get("line_items")
        if not line_items:
            try:
                full = _get_order(o["id"])
                line_items = full.get("line_items", [])
            except Exception:
                line_items = []
        matched = False
        names = []
        qty_sum = 0
        for item in line_items or []:
            item_sku = (item.get("sku") or "").strip()
            name = (item.get("name") or "")
            if sku_key and item_sku == sku_key:
                matched = True
            elif name_key and name_key in name.lower():
                matched = True
            else:
                continue
            names.append(name)
            try:
                qty_sum += int(item.get("quantity", 0))
            except (TypeError, ValueError):
                pass
        if not matched:
            continue

        billing = o.get("billing") or {}
        email = (billing.get("email") or "").strip()
        if not email:
            continue
        first_name = billing.get("first_name") or ""
        last_name = billing.get("last_name") or ""
        key = email.lower()
        entry = by_email.get(key)
        order_date = o.get("date_created") or ""
        total = o.get("total") or ""
        product_name = ", ".join(sorted(set(names))) if names else ""
        if entry is None:
            by_email[key] = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "order_id": o.get("id"),
                "order_date": order_date,
                "total": total,
                "product_name": product_name,
                "quantity": qty_sum,
            }
        else:
            # Accumulate quantities; keep earliest order_id and earliest order_date
            try:
                entry["quantity"] += qty_sum
            except Exception:
                entry["quantity"] = qty_sum
            if order_date and (not entry.get("order_date") or order_date < entry["order_date"]):
                entry["order_date"] = order_date
                entry["order_id"] = o.get("id")
            if product_name:
                have = set(entry.get("product_name", "").split(", ")) if entry.get("product_name") else set()
                have.update(product_name.split(", "))
                entry["product_name"] = ", ".join(sorted(x for x in have if x))
    return list(by_email.values())


def sales_today_for_product(product_name_substring):
    """
    Sum quantity sold today (completed + processing orders) for line items
    whose name contains product_name_substring (case-insensitive).
    Uses Hong Kong timezone for "today". Fetches each order by ID to ensure line_items.
    """
    orders = get_orders_today()
    return _sum_line_items_by_product(orders, product_name_substring)


def sales_report(from_date, to_date, product_name_substring=None, use_hk_time=True):
    """
    Sales (completed + processing) between from_date and to_date (date strings YYYY-MM-DD, inclusive).
    use_hk_time: interpret dates as Hong Kong midnight.
    Returns total quantity; if product_name_substring, only line items matching that name.
    """
    from datetime import timezone as tz_module
    if use_hk_time:
        hk = tz_module(timedelta(hours=8))
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=hk, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=hk, hour=23, minute=59, second=59, microsecond=999999)
    else:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)
    start_utc = start.astimezone(timezone.utc).isoformat()
    end_utc = end.astimezone(timezone.utc).isoformat()
    orders = _orders_in_range(start_utc, end_utc, statuses=["completed", "processing"])
    return _sum_line_items_by_product(orders, product_name_substring)


def main():
    parser = argparse.ArgumentParser(description="WooCommerce REST API – products, orders, stock, sales, reporting")
    parser.add_argument("--products", action="store_true", help="List products")
    parser.add_argument("--product", type=int, metavar="ID", help="Get one product by ID (name, price, stock)")
    parser.add_argument("--stock", action="store_true", help="List products with stock (id, name, stock_quantity, stock_status)")
    parser.add_argument("--orders", action="store_true", help="List orders")
    parser.add_argument("--sales-today", metavar="NAME", help="Quantity sold today for line items matching NAME")
    parser.add_argument("--sales-report", action="store_true", help="Sales in date range (use --from, --to; optional --report-product NAME)")
    parser.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD", help="Start date for --sales-report")
    parser.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", help="End date for --sales-report")
    parser.add_argument("--report-product", metavar="NAME", help="Filter --sales-report by line item name containing NAME")
    parser.add_argument(
        "--purchasers-between",
        action="store_true",
        help="Export unique purchaser emails between --from and --to (YYYY-MM-DD) as CSV for Meta audience upload",
    )
    parser.add_argument(
        "--customers-for-product",
        metavar="SKU",
        help="List unique customers between --from and --to who bought given SKU (or product name substring if SKU not present)",
    )
    parser.add_argument("--update-product", type=int, metavar="ID", help="Update product (use --set-stock, --set-price, --set-name)")
    parser.add_argument("--set-stock", type=int, metavar="N", help="Set stock_quantity to N (with --update-product)")
    parser.add_argument("--set-price", metavar="PRICE", help="Set regular_price (with --update-product)")
    parser.add_argument("--set-name", metavar="NAME", help="Set product name (with --update-product)")
    parser.add_argument("--adjust-stock", type=int, nargs=2, metavar=("ID", "DELTA"), help="Add/subtract stock: ID and +N or -N")
    parser.add_argument("-n", "--per-page", type=int, default=10, help="Number of items for list")
    parser.add_argument("--status", help="Filter orders by status (e.g. processing, completed)")
    args = parser.parse_args()

    if not any(
        [
            args.products,
            args.product,
            args.stock,
            args.orders,
            args.sales_today,
            args.sales_report,
            args.purchasers_between,
            args.customers_for_product,
            args.update_product is not None,
            args.adjust_stock,
        ]
    ):
        parser.print_help()
        return 0

    if args.product is not None:
        p = get_product(args.product)
        print("ID:", p.get("id"))
        print("Name:", p.get("name"))
        print("SKU:", p.get("sku", ""))
        print("Price:", p.get("price"), "| regular_price:", p.get("regular_price"))
        print("stock_quantity:", p.get("stock_quantity"), "| stock_status:", p.get("stock_status"), "| manage_stock:", p.get("manage_stock"))

    if args.stock:
        for p in get_products(per_page=args.per_page):
            print(p.get("id"), p.get("stock_quantity"), p.get("stock_status", ""), p.get("name", "?")[:45])

    if args.products:
        for p in get_products(per_page=args.per_page):
            print(p.get("id"), p.get("name", "?")[:50], p.get("price"), p.get("stock_status", ""))

    if args.purchasers_between:
        if not args.from_date or not args.to_date:
            raise SystemExit("--purchasers-between requires --from and --to (YYYY-MM-DD).")
        rows = purchasers_between(from_date=args.from_date, to_date=args.to_date)
        header = "email"
        try:
            print(header)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((header + "\n").encode("utf-8", errors="replace"))
        for r in rows:
            line = str(r.get("email", ""))
            try:
                print(line)
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))

    if args.customers_for_product:
        if not args.from_date or not args.to_date:
            raise SystemExit("--customers-for-product requires --from and --to (YYYY-MM-DD).")
        rows = customers_for_product_between(
            from_date=args.from_date,
            to_date=args.to_date,
            sku=args.customers_for_product,
            product_name_substring=args.report_product,
        )
        # CSV header
        header = "email,first_name,last_name,order_id,order_date,total,product_name,quantity"
        try:
            print(header)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((header + "\n").encode("utf-8", errors="replace"))
        for r in rows:
            line = ",".join(
                [
                    str(r.get("email", "")),
                    str(r.get("first_name", "")),
                    str(r.get("last_name", "")),
                    str(r.get("order_id", "")),
                    str(r.get("order_date", "")),
                    str(r.get("total", "")),
                    str(r.get("product_name", "")),
                    str(r.get("quantity", "")),
                ]
            )
            try:
                print(line)
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))

    if args.orders:
        for o in get_orders(per_page=args.per_page, status=args.status):
            print(o.get("id"), o.get("status"), o.get("date_created", "")[:10], o.get("total"))

    if args.sales_today:
        qty = sales_today_for_product(args.sales_today)
        print(qty)

    if args.sales_report:
        if not args.from_date or not args.to_date:
            print("Use --sales-report with --from YYYY-MM-DD and --to YYYY-MM-DD")
            return 1
        qty = sales_report(args.from_date, args.to_date, product_name_substring=args.report_product)
        print(qty)

    if args.update_product is not None:
        data = {}
        if args.set_stock is not None:
            data["stock_quantity"] = args.set_stock
            data["manage_stock"] = True
        if args.set_price is not None:
            data["regular_price"] = str(args.set_price)
        if args.set_name is not None:
            data["name"] = args.set_name
        if not data:
            print("Use --update-product ID with at least one of --set-stock, --set-price, --set-name")
            return 1
        updated = update_product(args.update_product, **data)
        print("Updated:", updated.get("id"), updated.get("name", "")[:40], "stock_quantity:", updated.get("stock_quantity"), "price:", updated.get("regular_price"))

    if args.adjust_stock:
        pid, delta = args.adjust_stock[0], args.adjust_stock[1]
        new_qty = adjust_stock(pid, delta)
        print("Product", pid, "stock adjusted by", delta, "-> new quantity:", new_qty)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
