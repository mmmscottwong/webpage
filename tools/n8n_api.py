"""
n8n REST API – list workflows, list executions, trigger workflow via webhook.
Uses N8N_BASE_URL and N8N_API_KEY from .env.
See workflows/n8n_setup.md.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

API_VERSION = "v1"
WEBHOOKS_JSON = _ROOT / "workflows" / "config" / "n8n_webhooks.json"


def load_webhook_table():
    """Load identity -> URL map from workflows/n8n_webhooks.json."""
    if not WEBHOOKS_JSON.exists():
        return {}
    try:
        with open(WEBHOOKS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in (data or {}).items() if isinstance(v, str) and k != "_comment"}
    except Exception:
        return {}


def get_webhook_url(identity):
    """Get webhook URL by identity from the table. identity is case-sensitive."""
    table = load_webhook_table()
    return table.get(identity)


def _base_url():
    url = (os.getenv("N8N_BASE_URL") or "").rstrip("/")
    if not url:
        raise SystemExit(
            "Set N8N_BASE_URL in .env (e.g. https://n8n.example.com). See workflows/n8n_setup.md."
        )
    return url


def _api_key():
    key = os.getenv("N8N_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "Set N8N_API_KEY in .env (from n8n Settings → n8n API). See workflows/n8n_setup.md."
        )
    return key


def _headers():
    return {
        "X-N8N-API-KEY": _api_key(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _get(path, params=None):
    url = f"{_base_url()}/api/{API_VERSION}{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path, json_body):
    url = f"{_base_url()}/api/{API_VERSION}{path}"
    r = requests.post(url, headers=_headers(), json=json_body, timeout=30)
    r.raise_for_status()
    return r.json()


def _put(path, json_body):
    url = f"{_base_url()}/api/{API_VERSION}{path}"
    r = requests.put(url, headers=_headers(), json=json_body, timeout=30)
    r.raise_for_status()
    return r.json()


def update_workflow(workflow_id, body):
    """
    Update workflow by ID. body must be full workflow (name, nodes, connections, settings).
    Use get_workflow(id) to get current, modify, then pass here. API does not support PATCH.
    """
    return _put(f"/workflows/{workflow_id}", body)


def list_workflows(active=None, limit=20):
    """List workflows. active: True/False to filter by active status."""
    params = {"limit": limit}
    if active is not None:
        params["active"] = str(active).lower()
    return _get("/workflows", params)


def get_workflow(workflow_id):
    """Get a single workflow by ID (includes nodes with parameters)."""
    return _get(f"/workflows/{workflow_id}")


def get_webhook_urls():
    """
    List all workflows, find Webhook nodes, and print production URLs.
    Uses workflow nodes' path parameter: {N8N_BASE_URL}/webhook/{path}
    """
    data = list_workflows(limit=100)
    workflows = data.get("data", [])
    base = _base_url().rstrip("/")
    out = []
    for w in workflows:
        wid = w.get("id")
        name = w.get("name", "?")
        active = w.get("active", False)
        try:
            full = get_workflow(wid)
        except Exception:
            continue
        payload = full.get("data", full)
        if not isinstance(payload, dict):
            continue
        nodes = payload.get("nodes", [])
        for node in nodes:
            if "webhook" in (node.get("type") or "").lower():
                path = (node.get("parameters") or {}).get("path") or node.get("webhookId") or "(no path)"
                url = f"{base}/webhook/{path}"
                out.append((name, wid, active, url))
                break
    return out


def list_executions(workflow_id=None, status=None, limit=20):
    """List executions. workflow_id: filter by workflow; status: e.g. success, error."""
    params = {"limit": limit}
    if workflow_id:
        params["workflowId"] = workflow_id
    if status:
        params["status"] = status
    return _get("/executions", params)


def create_webhook_workflow(name="Agent Webhook Trigger", path="agent-trigger"):
    """
    Create a workflow with one Webhook trigger (POST) and one Respond to Webhook (JSON).
    Returns the created workflow (with id). After creating, activate it in n8n to get the webhook URL.
    """
    payload = {
        "name": name,
        "nodes": [
            {
                "id": "webhook-node",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [240, 300],
                "parameters": {"path": path, "httpMethod": "POST", "responseMode": "responseNode"},
            },
            {
                "id": "respond-node",
                "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1.1,
                "position": [460, 300],
                "parameters": {
                    "respondWith": "json",
                    "responseBody": '{"ok": true, "message": "Agent webhook received"}',
                },
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
            }
        },
        "settings": {},
    }
    return _post("/workflows", payload)


def trigger_webhook(webhook_url, data=None):
    """POST to a webhook URL (e.g. https://n8n.example.com/webhook/xxx). data: dict or None."""
    r = requests.post(
        webhook_url,
        json=data or {},
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    if r.status_code == 404:
        msg = (
            "404 Not Found.\n"
            "• If n8n is behind Cloudflare Access, 404 often means the request is blocked. "
            "In Cloudflare Zero Trust → Access → your n8n app → add a Bypass rule for path /webhook/* (no login).\n"
            "• Or in n8n: open the workflow → click the Webhook node → copy the exact 'Production URL' and use that with --trigger."
        )
        raise SystemExit(msg)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text[:500]}


def main():
    parser = argparse.ArgumentParser(
        description="n8n API – list workflows, executions; trigger webhook"
    )
    parser.add_argument("--workflows", action="store_true", help="List workflows")
    parser.add_argument("--executions", action="store_true", help="List recent executions")
    parser.add_argument("--trigger", metavar="WEBHOOK_URL", help="POST to webhook URL to trigger a workflow")
    parser.add_argument("--data", metavar="JSON", help="JSON body for --trigger (e.g. \'{\"key\":\"value\"}\')")
    parser.add_argument("-n", "--limit", type=int, default=20, help="Max items for list (default 20)")
    parser.add_argument("--active", action="store_true", help="Only active workflows (with --workflows)")
    parser.add_argument("--workflow-id", metavar="ID", help="Filter executions by workflow ID")
    parser.add_argument(
        "--create-webhook-workflow",
        action="store_true",
        help="Create a workflow with Webhook trigger (path: agent-trigger). Then activate it in n8n to get the URL.",
    )
    parser.add_argument("--webhook-path", default="agent-trigger", help="Webhook path for --create-webhook-workflow")
    parser.add_argument(
        "--webhook-urls",
        action="store_true",
        help="Print production webhook URLs for all workflows that have a Webhook node (and whether active).",
    )
    parser.add_argument(
        "--trigger-test",
        metavar="URL",
        help="POST to URL and show status + response (no exit on error). Use to see if you get HTML (Cloudflare) or JSON (n8n).",
    )
    parser.add_argument(
        "--trigger-by-name",
        metavar="IDENTITY",
        help="Trigger webhook by identity from workflows/n8n_webhooks.json (e.g. agent-trigger).",
    )
    parser.add_argument(
        "--list-webhooks",
        action="store_true",
        help="List registered webhook identities from workflows/n8n_webhooks.json.",
    )
    parser.add_argument("--get-workflow", metavar="ID", help="Get full workflow JSON by ID (for edit/optimize).")
    parser.add_argument("--update-workflow", metavar="ID", help="Update workflow by ID; body from --file (full JSON).")
    parser.add_argument("--file", dest="input_file", metavar="PATH", help="Path to JSON file (for --update-workflow).")
    args = parser.parse_args()

    if not any([args.workflows, args.executions, args.trigger, args.create_webhook_workflow, args.webhook_urls, args.trigger_test, args.trigger_by_name, args.list_webhooks, args.get_workflow, args.update_workflow]):
        parser.print_help()
        return 0

    if args.workflows:
        active = True if args.active else None
        data = list_workflows(active=active, limit=args.limit)
        for w in data.get("data", []):
            print(w.get("id"), "active:", w.get("active"), w.get("name", "?"))

    if args.executions:
        data = list_executions(
            workflow_id=args.workflow_id,
            limit=args.limit,
        )
        for e in data.get("data", []):
            print(
                e.get("id"),
                "workflow:", e.get("workflowId"),
                "status:", e.get("status"),
                "started:", (e.get("startedAt") or "")[:19],
            )

    if args.trigger:
        body = None
        if args.data:
            try:
                body = json.loads(args.data)
            except json.JSONDecodeError:
                print("Invalid --data JSON")
                return 1
        result = trigger_webhook(args.trigger, data=body)
        if isinstance(result, dict):
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        else:
            print(result)

    if args.create_webhook_workflow:
        try:
            w = create_webhook_workflow(path=args.webhook_path)
            data = w.get("data", w)
            wid = data.get("id") if isinstance(data, dict) else None
            print("Workflow created. ID:", wid or "(see n8n UI)")
            base = _base_url()
            print("Next: open n8n → find workflow 'Agent Webhook Trigger' → Activate it.")
            print("Then your webhook URL will be:", f"{base}/webhook/{args.webhook_path}")
        except requests.exceptions.HTTPError as e:
            print("Create failed:", e.response.status_code, e.response.text[:300])
            return 1

    if args.webhook_urls:
        try:
            rows = get_webhook_urls()
            if not rows:
                print("No workflows with a Webhook node found.")
            else:
                for name, wid, active, url in rows:
                    print("active:", active, "|", name, "|", url)
                print("\nUse the URL above with: py tools/n8n_api.py --trigger \"<URL>\"")
        except requests.exceptions.HTTPError as e:
            print("Failed to list workflows:", e.response.status_code, e.response.text[:200])
            return 1

    if args.trigger_test:
        url = args.trigger_test
        try:
            r = requests.post(url, json={}, headers={"Content-Type": "application/json"}, timeout=15)
            print("Status:", r.status_code)
            body = r.text[:400] if r.text else "(empty)"
            if "html" in (r.headers.get("Content-Type") or "").lower() or body.strip().startswith("<!") or body.strip().startswith("<html"):
                print("Response: HTML (likely Cloudflare login page – bypass /webhook/* in Access)")
            else:
                print("Response:", body)
        except Exception as e:
            print("Error:", e)
        return 0

    if args.list_webhooks:
        table = load_webhook_table()
        if not table:
            print("No webhooks in workflows/n8n_webhooks.json. Add entries: {\"identity\": \"https://...\"}")
        else:
            for name, url in table.items():
                print(name, "->", url)
        return 0

    if args.trigger_by_name:
        url = get_webhook_url(args.trigger_by_name)
        if not url:
            table = load_webhook_table()
            print("Unknown identity:", args.trigger_by_name)
            if table:
                print("Known:", ", ".join(table.keys()))
            else:
                print("Add entries to workflows/n8n_webhooks.json")
            return 1
        body = None
        if args.data:
            try:
                body = json.loads(args.data)
            except json.JSONDecodeError:
                print("Invalid --data JSON")
                return 1
        try:
            result = trigger_webhook(url, data=body)
            if isinstance(result, dict):
                print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
            else:
                print(result)
        except SystemExit:
            raise
        except Exception as e:
            print("Error:", e)
            return 1
        return 0

    if args.get_workflow:
        try:
            raw = get_workflow(args.get_workflow)
            payload = raw.get("data", raw)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        except requests.exceptions.HTTPError as e:
            print("Error:", e.response.status_code, e.response.text[:300])
            return 1
        return 0

    if args.update_workflow:
        if not args.input_file or not Path(args.input_file).exists():
            print("Use --update-workflow ID --file path/to/workflow.json (full workflow JSON)")
            return 1
        try:
            with open(args.input_file, encoding="utf-8") as f:
                body = json.load(f)
            payload = body.get("data", body) if isinstance(body.get("data"), dict) else body
            out = update_workflow(args.update_workflow, payload)
            print("Updated:", out.get("data", out).get("name", args.update_workflow))
        except requests.exceptions.HTTPError as e:
            print("Error:", e.response.status_code, e.response.text[:300])
            return 1
        except FileNotFoundError:
            print("File not found:", args.input_file)
            return 1
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
