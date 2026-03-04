"""
Google Analytics 4 (GA4) Data API – list properties and run reports.
Uses shared credentials from google_auth (run google_auth.py once).
Set GA4_PROPERTY_ID in .env for reporting (e.g. 123456789).
"""
import argparse
import os
import sys
from pathlib import Path

from googleapiclient.discovery import build

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from tools.google_auth import get_credentials, run_oauth_flow


def get_ga4_service():
    creds = get_credentials()
    if not creds or not creds.valid:
        run_oauth_flow()
        creds = get_credentials()
    return build("analyticsdata", "v1beta", credentials=creds)


def run_report(service, property_id, dimensions=None, metrics=None, date_ranges=None):
    """
    Run a simple GA4 report.
    dimensions/metrics: lists of GA4 dimension/metric names, e.g. ['date'], ['activeUsers'].
    """
    body = {
        "property": f"properties/{property_id}",
        "dateRanges": date_ranges or [{"startDate": "7daysAgo", "endDate": "today"}],
    }
    if dimensions:
        body["dimensions"] = [{"name": d} for d in dimensions]
    if metrics:
        body["metrics"] = [{"name": m} for m in metrics]
    return service.properties().runReport(body=body).execute()


def list_properties(creds=None):
    """List GA4 properties (uses Analytics Admin API)."""
    if creds is None:
        creds = get_credentials()
        if not creds or not creds.valid:
            run_oauth_flow()
            creds = get_credentials()
    admin = build("analyticsadmin", "v1beta", credentials=creds)
    accounts = admin.accountSummaries().list().execute()
    out = []
    for acc in accounts.get("accountSummaries", []):
        for prop in acc.get("propertySummaries", []):
            out.append({"account": acc.get("displayName"), "property": prop.get("displayName"), "id": prop.get("property", "").replace("properties/", "")})
    return out


def main():
    parser = argparse.ArgumentParser(description="GA4 – list properties or run a report")
    parser.add_argument("--list-properties", action="store_true", help="List GA4 property IDs")
    parser.add_argument("--report", action="store_true", help="Run a simple report (requires GA4_PROPERTY_ID in .env)")
    parser.add_argument("--property-id", help="Override GA4 property ID")
    args = parser.parse_args()

    if not args.list_properties and not args.report:
        parser.print_help()
        return 0

    if args.list_properties:
        for p in list_properties():
            print(p["id"], p["property"], p["account"])

    if args.report:
        property_id = args.property_id or os.environ.get("GA4_PROPERTY_ID")
        if not property_id:
            print("Set GA4_PROPERTY_ID in .env or pass --property-id")
            return 1
        service = get_ga4_service()
        result = run_report(service, property_id, dimensions=["date"], metrics=["activeUsers"])
        for row in result.get("rows", []):
            dims = [d.get("value", "") for d in row.get("dimensionValues", [])]
            mets = [m.get("value", "") for m in row.get("metricValues", [])]
            print("\t".join(dims + mets))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
