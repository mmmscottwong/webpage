# Workflow: Set up n8n workflow from this project (current version)

## Objective
Use this project to create or update n8n workflows so they match a known-good format. You can either **import the template** or **export from your n8n (current version)** and then edit/update via the tool.

## Option A: Import the template (no API needed)

1. Open n8n → **Workflows** → **⋯** → **Import from File**.
2. Choose **`workflows/n8n_webhook_workflow.json`** from this project.
3. In the imported workflow, **Save** then **Activate** (Published).
4. The webhook path is **agent-trigger-v2**. Add to **`workflows/n8n_webhooks.json`**:
   ```json
   "agent-trigger": "https://n8n.pipucapyonline.com/webhook/agent-trigger-v2"
   ```
5. Test: `py tools/n8n_api.py --trigger-by-name agent-trigger`

The template uses **Webhook (typeVersion 2)** + **Respond to Webhook (typeVersion 1.1)**, compatible with current n8n.

---

## Option B: Export current version from n8n, then edit/update via API

When the n8n API is reachable from your machine (same network or after Cloudflare etc.):

### 1. List workflows and get IDs

```powershell
py tools/n8n_api.py --workflows
```

Note the **id** of the workflow you want to base on (e.g. "Agent Webhook Trigger").

### 2. Export full workflow JSON (current version)

```powershell
py tools/n8n_api.py --get-workflow <WORKFLOW_ID> > .tmp/workflow_current.json
```

This file is the **current version** of that workflow in n8n (nodes, connections, settings). You can use it as the baseline for edits.

### 3. Edit the JSON (you or Agent)

- Open `.tmp/workflow_current.json`.
- Change what you need (add nodes, change parameters, connections, settings). Keep the overall structure (name, nodes, connections, settings).
- Save the file.

### 4. Push back to n8n

```powershell
py tools/n8n_api.py --update-workflow <WORKFLOW_ID> --file .tmp/workflow_current.json
```

### 5. In n8n

- Check the workflow in the editor. If it has a Webhook trigger, do **Unpublish → Publish** once.
- Test the webhook URL.

---

## Option C: Create a new workflow via API (same format as template)

```powershell
py tools/n8n_api.py --create-webhook-workflow --webhook-path agent-trigger-v2
```

Then in n8n: find the new workflow → **Activate** it. Register the URL in **`workflows/n8n_webhooks.json`** if you want to use `--trigger-by-name`.

---

## Summary

| Method | When to use |
|--------|-------------|
| **A: Import template** | Quick setup; no API; use `workflows/n8n_webhook_workflow.json`. |
| **B: Export → edit → update** | You want to change an existing workflow; Agent can edit the exported JSON and you run `--update-workflow`. |
| **C: Create via API** | You want a new webhook workflow from the project; API must be reachable. |

The **current version** of a workflow is whatever n8n returns from **`--get-workflow <id>`**. Use that JSON as the baseline when you ask the Agent to “set up or optimize based on current version.”
