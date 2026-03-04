"""
HubSpot CRM API – contacts, companies, deals, search (CRM segmentation).
Uses Private App access token from .env (HUBSPOT_ACCESS_TOKEN).
See workflows/hubspot_setup.md.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

BASE_URL = "https://api.hubapi.com"


def _token():
    t = os.getenv("HUBSPOT_ACCESS_TOKEN", "").strip()
    if not t:
        raise SystemExit(
            "Set HUBSPOT_ACCESS_TOKEN in .env (Private App token from HubSpot Settings → Integrations → Private Apps). "
            "See workflows/hubspot_setup.md."
        )
    return t


def _headers():
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


def _get(path, params=None):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path, body):
    url = f"{BASE_URL}{path}"
    r = requests.post(url, headers=_headers(), json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def _list_objects(object_type, limit=10, after=None, properties=None, associations=None):
    """List CRM objects (contacts, companies, deals, line_items)."""
    path = f"/crm/v3/objects/{object_type}"
    params = {"limit": min(limit, 100)}
    if after:
        params["after"] = after
    if properties:
        params["properties"] = ",".join(properties)
    if associations:
        params["associations"] = ",".join(associations)
    return _get(path, params)


def get_contacts(limit=10, after=None):
    """List contacts. Returns dict with results and paging."""
    props = ["email", "firstname", "lastname", "company", "phone", "createdate"]
    return _list_objects("contacts", limit=limit, after=after, properties=props)


def get_companies(limit=10, after=None):
    """List companies. Returns dict with results and paging."""
    props = ["name", "domain", "industry", "createdate", "amount"]
    return _list_objects("companies", limit=limit, after=after, properties=props)


def get_deals(limit=10, after=None):
    """List deals. Returns dict with results and paging."""
    props = ["dealname", "dealstage", "amount", "closedate", "createdate", "pipeline"]
    return _list_objects("deals", limit=limit, after=after, properties=props, associations=["contacts", "line_items"])


def get_contact(contact_id):
    """Get a single contact by ID."""
    return _get(f"/crm/v3/objects/contacts/{contact_id}", {"properties": "email,firstname,lastname,company,phone"})


def get_company(company_id):
    """Get a single company by ID."""
    return _get(f"/crm/v3/objects/companies/{company_id}", {"properties": "name,domain,industry,amount"})


def get_deal(deal_id):
    """Get a single deal by ID."""
    return _get(
        f"/crm/v3/objects/deals/{deal_id}",
        {"properties": "dealname,dealstage,amount,closedate,pipeline", "associations": "contacts,line_items"},
    )


def get_line_items(limit=10, after=None):
    """List line items. Returns dict with results and paging."""
    props = [
        "name",
        "hs_product_id",
        "hs_sku",
        "quantity",
        "price",
        "amount",
        "createdate",
        "hs_lastmodifieddate",
    ]
    return _list_objects("line_items", limit=limit, after=after, properties=props, associations=["deals", "contacts"])


def get_line_item(line_item_id):
    """Get a single line item by ID."""
    return _get(
        f"/crm/v3/objects/line_items/{line_item_id}",
        {
            "properties": "name,hs_product_id,hs_sku,quantity,price,amount,createdate,hs_lastmodifieddate",
            "associations": "deals,contacts",
        },
    )


def search_line_items_by_name_in_range(from_date, to_date, name_substring, max_pages=20):
    """
    Search line items where name contains name_substring AND createdate between from_date/to_date (YYYY-MM-DD).
    Returns list of line item objects with properties and associations.
    """
    tz = timezone.utc
    start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=tz, hour=0, minute=0, second=0, microsecond=0)
    end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=tz, hour=23, minute=59, second=59, microsecond=999999)
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    items = []
    after = None
    pages = 0
    while pages < max_pages:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "createdate", "operator": "GTE", "value": start_iso},
                        {"propertyName": "createdate", "operator": "LTE", "value": end_iso},
                        {"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": name_substring},
                    ]
                }
            ],
            "properties": [
                "name",
                "hs_product_id",
                "hs_sku",
                "quantity",
                "price",
                "amount",
                "createdate",
                "hs_lastmodifieddate",
            ],
            "limit": 100,
        }
        if after:
            body["after"] = after
        # Ask for deals & contacts associations so we know which orders/contacts are linked
        res = _post("/crm/v3/objects/line_items/search?associations=deals,contacts", body)
        batch = res.get("results", []) or []
        items.extend(batch)
        paging = res.get("paging", {})
        after = paging.get("next", {}).get("after")
        pages += 1
        if not after or not batch:
            break
    return items


def search_contacts(filter_groups, properties=None, limit=100, after=None):
    """
    Search contacts via CRM Search API.
    filter_groups: list of dicts, each with "filters" list; each filter has propertyName, operator, value (or values for BETWEEN).
    properties: optional list of property names to return.
    Returns dict with results, total, paging.
    """
    body = {"filterGroups": filter_groups, "limit": min(limit, 100)}
    if properties:
        body["properties"] = properties
    if after:
        body["after"] = after
    return _post("/crm/v3/objects/contacts/search", body)


def search_deals_by_closedate(from_date, to_date, pipeline_id=None, limit=5000):
    """
    Search deals with closedate between from_date and to_date (YYYY-MM-DD).
    Optional pipeline_id to restrict to a pipeline (e.g. online store).
    Returns list of deal objects with id and properties (dealname, closedate, amount, pipeline).
    """
    tz = timezone.utc
    start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=tz, hour=0, minute=0, second=0, microsecond=0)
    end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=tz, hour=23, minute=59, second=59, microsecond=999999)
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    filters = [
        {"propertyName": "closedate", "operator": "GTE", "value": start_iso},
        {"propertyName": "closedate", "operator": "LTE", "value": end_iso},
    ]
    if pipeline_id is not None:
        filters.append({"propertyName": "pipeline", "operator": "EQ", "value": str(pipeline_id)})

    deals = []
    after = None
    page_size = 100
    while len(deals) < limit:
        body = {
            "filterGroups": [{"filters": filters}],
            "properties": ["dealname", "closedate", "amount", "pipeline"],
            "limit": page_size,
        }
        if after:
            body["after"] = after
        res = _post("/crm/v3/objects/deals/search", body)
        batch = res.get("results", []) or []
        deals.extend(batch)
        after = res.get("paging", {}).get("next", {}).get("after")
        if not after or not batch:
            break
    return deals[:limit]


def get_contact_ids_for_deals(deal_ids, batch_size=100):
    """
    Return set of contact IDs associated with the given deal IDs.
    Uses POST /crm/v4/associations/deal/contact/batch/read.
    """
    contact_ids = set()
    for i in range(0, len(deal_ids), batch_size):
        chunk = deal_ids[i : i + batch_size]
        body = {"inputs": [{"id": str(d)} for d in chunk]}
        res = _post("/crm/v4/associations/deal/contact/batch/read", body)
        for rec in res.get("results", []) or []:
            for to_obj in rec.get("to", []) or []:
                cid = to_obj.get("toObjectId")
                if cid:
                    contact_ids.add(cid)
    return contact_ids


def get_contacts_batch(contact_ids, properties=None):
    """
    Fetch multiple contacts by ID. contact_ids: list of (string or int) IDs.
    Returns list of contact objects with id and properties.
    """
    if not contact_ids:
        return []
    props = properties or ["email", "firstname", "lastname", "company", "phone", "createdate"]
    out = []
    batch_size = 100
    for i in range(0, len(contact_ids), batch_size):
        chunk = contact_ids[i : i + batch_size]
        body = {"inputs": [{"id": str(c)} for c in chunk], "properties": props}
        res = _post("/crm/v3/objects/contacts/batch/read", body)
        for obj in res.get("results", []) or []:
            out.append(obj)
    return out


def get_contacts_with_deals_closed_in_range(from_date, to_date, pipeline_id=None):
    """
    Return list of contacts who have at least one deal closed between from_date and to_date (YYYY-MM-DD).
    Each contact dict: id, properties (email, firstname, lastname, company, phone), and optionally deal_count, last_closedate.
    """
    deals = search_deals_by_closedate(from_date, to_date, pipeline_id=pipeline_id)
    if not deals:
        return []
    deal_ids = [d.get("id") for d in deals if d.get("id")]
    contact_ids = list(get_contact_ids_for_deals(deal_ids))
    if not contact_ids:
        return []
    return get_contacts_batch(contact_ids)


def get_yesterday_engagement_contacts(limit=1000, use_lastmodified_fallback=True):
    """
    Return contacts with engagement (or record update) in the last calendar day (yesterday).
    Tries hs_lastengagementdate first; falls back to lastmodifieddate if needed.
    limit: max contacts to return (paginates internally).
    Returns list of contact objects with id, properties.
    """
    tz = timezone.utc
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    start_ts = f"{yesterday.isoformat()}T00:00:00.000Z"
    end_ts = f"{yesterday.isoformat()}T23:59:59.999Z"

    props = [
        "email",
        "firstname",
        "lastname",
        "company",
        "phone",
        "createdate",
        "lastmodifieddate",
        "hs_lastengagementdate",
        "hs_last_sales_activity_date",
        # Analytics / ad-source-style fields for richer segmentation
        "hs_analytics_source",
        "hs_analytics_source_data_1",
        "hs_analytics_source_data_2",
        "hs_analytics_latest_source",
        "hs_analytics_latest_source_data_1",
        "hs_analytics_latest_source_data_2",
    ]
    filter_by_engagement = {
        "filters": [
            {"propertyName": "hs_lastengagementdate", "operator": "GTE", "value": start_ts},
            {"propertyName": "hs_lastengagementdate", "operator": "LTE", "value": end_ts},
        ]
    }
    filter_by_modified = {
        "filters": [
            {"propertyName": "lastmodifieddate", "operator": "GTE", "value": start_ts},
            {"propertyName": "lastmodifieddate", "operator": "LTE", "value": end_ts},
        ]
    }

    out = []
    after = None
    page_size = 100

    def fetch(filters):
        nonlocal after
        body = {
            "filterGroups": [{"filters": filters}],
            "properties": props,
            "limit": page_size,
        }
        if after:
            body["after"] = after
        data = _post("/crm/v3/objects/contacts/search", body)
        after = data.get("paging", {}).get("next", {}).get("after")
        return data.get("results", []), data.get("total", 0)

    # Try engagement date first
    try:
        while len(out) < limit:
            batch, total = fetch(filter_by_engagement["filters"])
            out.extend(batch)
            if not after or not batch:
                break
        if out:
            return out[:limit]
    except Exception:
        pass

    # Fallback: lastmodifieddate (contacts updated yesterday)
    if use_lastmodified_fallback:
        after = None
        out = []
        try:
            while len(out) < limit:
                batch, _ = fetch(filter_by_modified["filters"])
                out.extend(batch)
                if not after or not batch:
                    break
        except Exception:
            pass

    return out[:limit]


def get_yesterday_email_engagement_summaries(max_emails=5000):
    """
    Return a mapping contact_id -> summary of latest email engagement from yesterday.

    Summary keys:
      hs_timestamp, hs_email_subject, hs_email_direction, hs_email_status,
      hs_email_from_email, hs_email_to_email
    """
    tz = timezone.utc
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    start_ts = f"{yesterday.isoformat()}T00:00:00.000Z"
    end_ts = f"{yesterday.isoformat()}T23:59:59.999Z"

    props = [
        "hs_timestamp",
        "hs_email_subject",
        "hs_email_direction",
        "hs_email_status",
        "hs_email_from_email",
        "hs_email_to_email",
    ]

    summaries = {}
    after = None
    page_size = 100

    def fetch():
        nonlocal after
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "hs_timestamp", "operator": "GTE", "value": start_ts},
                        {"propertyName": "hs_timestamp", "operator": "LTE", "value": end_ts},
                    ]
                }
            ],
            "properties": props,
            "limit": page_size,
        }
        if after:
            body["after"] = after
        # Ask for contact associations so we can map back to contacts
        data = _post("/crm/v3/objects/emails/search?associations=contacts", body)
        after = data.get("paging", {}).get("next", {}).get("after")
        return data.get("results", [])

    fetched = 0
    while fetched < max_emails:
        batch = fetch()
        if not batch:
            break
        for e in batch:
            fetched += 1
            if fetched > max_emails:
                break
            props_e = e.get("properties", {}) or {}
            ts = props_e.get("hs_timestamp")
            # Associations -> contacts
            assoc_contacts = (
                e.get("associations", {})
                .get("contacts", {})
                .get("results", [])
            )
            if not assoc_contacts or not ts:
                continue
            contact_id = assoc_contacts[0].get("id")
            if not contact_id:
                continue
            prev = summaries.get(contact_id)
            if prev is None or (ts and ts > prev.get("hs_timestamp", "")):
                summaries[contact_id] = {
                    "hs_timestamp": ts,
                    "hs_email_subject": props_e.get("hs_email_subject", ""),
                    "hs_email_direction": props_e.get("hs_email_direction", ""),
                    "hs_email_status": props_e.get("hs_email_status", ""),
                    "hs_email_from_email": props_e.get("hs_email_from_email", ""),
                    "hs_email_to_email": props_e.get("hs_email_to_email", ""),
                }
        if not after:
            break

    return summaries


def main():
    parser = argparse.ArgumentParser(description="HubSpot CRM API – contacts, companies, deals, line items, segmentation")
    parser.add_argument("--contacts", action="store_true", help="List contacts")
    parser.add_argument("--companies", action="store_true", help="List companies")
    parser.add_argument("--deals", action="store_true", help="List deals")
    parser.add_argument("--contact", type=str, metavar="ID", help="Get one contact by ID")
    parser.add_argument("--company", type=str, metavar="ID", help="Get one company by ID")
    parser.add_argument("--deal", type=str, metavar="ID", help="Get one deal by ID")
    parser.add_argument("--line-items", action="store_true", help="List line items")
    parser.add_argument("--line-item", type=str, metavar="ID", help="Get one line item by ID")
    parser.add_argument(
        "--line-items-search",
        action="store_true",
        help="Search line items by name + createdate range (use --name, --from, --to)",
    )
    parser.add_argument("--name", metavar="NAME", help="Name substring for --line-items-search")
    parser.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD", help="Start date for --line-items-search")
    parser.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", help="End date for --line-items-search")
    parser.add_argument("--engagement-yesterday", action="store_true", help="List contacts with engagement yesterday (CRM segmentation)")
    parser.add_argument("--contacts-purchased-in-month", type=str, metavar="YYYY-MM", help="Contacts with at least one deal closed in this month (e.g. 2025-12)")
    parser.add_argument("--pipeline-id", type=str, metavar="ID", help="Optional pipeline ID to filter deals (e.g. online store)")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max items to list (default 10)")
    parser.add_argument("-o", "--out", type=str, metavar="FILE", help="Write engagement list JSON to file (e.g. .tmp/yesterday_engagement.json)")
    args = parser.parse_args()

    if not any(
        [
            args.contacts,
            args.companies,
            args.deals,
            args.line_items,
            args.contact,
            args.company,
            args.deal,
            args.line_item,
            args.line_items_search,
            args.engagement_yesterday,
            args.contacts_purchased_in_month,
        ]
    ):
        parser.print_help()
        return 0

    if args.contacts_purchased_in_month:
        try:
            year, month = args.contacts_purchased_in_month.strip().split("-")
            from_date = f"{year}-{month}-01"
            # last day of month
            end = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
            if month == "12":
                end = end.replace(year=end.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = end.replace(month=end.month + 1, day=1) - timedelta(days=1)
            to_date = end.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            raise SystemExit("--contacts-purchased-in-month must be YYYY-MM (e.g. 2025-12)")
        pipeline_id = args.pipeline_id.strip() if args.pipeline_id else None
        contacts = get_contacts_with_deals_closed_in_range(from_date, to_date, pipeline_id=pipeline_id)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=2, ensure_ascii=False)
            print(f"Wrote {len(contacts)} contacts to {out_path}", file=sys.stderr)
        print(f"# Contacts with deal closed in {args.contacts_purchased_in_month}: {len(contacts)}")
        for c in contacts:
            props = c.get("properties", {}) or {}
            line = "\t".join(
                [
                    str(c.get("id", "")),
                    props.get("email") or "",
                    props.get("firstname") or "",
                    props.get("lastname") or "",
                    props.get("company") or "",
                    props.get("phone") or "",
                ]
            )
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", errors="replace").decode("ascii"))
        return 0

    if args.engagement_yesterday:
        contacts = get_yesterday_engagement_contacts(limit=args.limit)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=2, ensure_ascii=False)
            print(f"Wrote {len(contacts)} contacts to {out_path}", file=sys.stderr)
        print(f"# Yesterday engagement: {len(contacts)} contacts")
        for c in contacts:
            props = c.get("properties", {})
            row = (
                str(c.get("id", "")),
                (props.get("email") or ""),
                (props.get("firstname") or ""),
                (props.get("lastname") or ""),
                (props.get("company") or ""),
                (props.get("hs_lastengagementdate") or props.get("lastmodifieddate") or ""),
            )
            line = "\t".join(str(x) for x in row)
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", errors="replace").decode("ascii"))

    if args.contacts:
        data = get_contacts(limit=args.limit)
        for c in data.get("results", []):
            props = c.get("properties", {})
            print(c.get("id"), props.get("email", ""), props.get("firstname", ""), props.get("lastname", ""), props.get("company", ""))

    if args.companies:
        data = get_companies(limit=args.limit)
        for c in data.get("results", []):
            props = c.get("properties", {})
            print(c.get("id"), props.get("name", ""), props.get("domain", ""), props.get("industry", ""))

    if args.deals:
        data = get_deals(limit=args.limit)
        for d in data.get("results", []):
            props = d.get("properties", {})
            print(d.get("id"), props.get("dealname", ""), props.get("dealstage", ""), props.get("amount", ""), props.get("closedate", ""))

    if args.line_items:
        data = get_line_items(limit=args.limit)
        for li in data.get("results", []):
            props = li.get("properties", {})
            print(
                li.get("id"),
                props.get("name", ""),
                props.get("hs_sku", ""),
                props.get("quantity", ""),
                props.get("amount", ""),
            )

    if args.contact:
        c = get_contact(args.contact)
        props = c.get("properties", {})
        print("ID:", c.get("id"))
        print("Email:", props.get("email"))
        print("First:", props.get("firstname"), "Last:", props.get("lastname"))
        print("Company:", props.get("company"), "Phone:", props.get("phone"))

    if args.company:
        c = get_company(args.company)
        props = c.get("properties", {})
        print("ID:", c.get("id"))
        print("Name:", props.get("name"), "Domain:", props.get("domain"))
        print("Industry:", props.get("industry"), "Amount:", props.get("amount"))

    if args.deal:
        d = get_deal(args.deal)
        props = d.get("properties", {})
        print("ID:", d.get("id"))
        print("Name:", props.get("dealname"), "Stage:", props.get("dealstage"))
        print("Amount:", props.get("amount"), "Close:", props.get("closedate"), "Pipeline:", props.get("pipeline"))

    if args.line_item:
        li = get_line_item(args.line_item)
        props = li.get("properties", {})
        print("ID:", li.get("id"))
        print("Name:", props.get("name"))
        print("SKU:", props.get("hs_sku"))
        print("Quantity:", props.get("quantity"), "Amount:", props.get("amount"))

    if args.line_items_search:
        if not args.name or not args.from_date or not args.to_date:
            raise SystemExit("--line-items-search requires --name, --from, and --to.")
        items = search_line_items_by_name_in_range(args.from_date, args.to_date, args.name)
        print(f"# Line items found: {len(items)}")
        for li in items:
            props = li.get("properties", {}) or {}
            print(
                li.get("id"),
                props.get("name", ""),
                props.get("hs_sku", ""),
                props.get("quantity", ""),
                props.get("amount", ""),
                props.get("createdate", ""),
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
