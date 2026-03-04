# Workflows

Markdown SOPs that define objectives, required inputs, which tools to use, expected outputs, and how to handle edge cases.

- One workflow per task or process.
- Written in plain language, like briefing a teammate.
- Keep workflows current as you learn (rate limits, quirks, better methods).
- Use `_template.md` when creating a new workflow.

---

## Directory Structure

```
workflows/
  README.md                      ← this file
  _template.md                   ← blank SOP template
  setup/                         ← one-time integration setup guides
  booking/                       ← email-to-calendar booking agent SOPs
  config/                        ← JSON config files used by tools
```

---

## setup/

One-time guides for connecting each external service.

| File | Purpose |
|------|---------|
| `google_setup.md` | OAuth2 setup for all Google APIs (Calendar, Gmail, Drive, Sheets, Slides, GA4) |
| `hubspot_setup.md` | HubSpot Private App token, required scopes, first-run verification |
| `meta_insights_setup.md` | Meta Business Suite — System User token, Page ID, IG Business ID |
| `meta_audience_create.md` | Meta Custom Audiences — Ad Account setup, CSV email upload workflow |
| `n8n_setup.md` | n8n instance setup, API key, webhook configuration |
| `n8n_setup_from_project.md` | Importing an existing n8n workflow from this project |
| `wordpress_setup.md` | WordPress Application Password + WooCommerce REST API keys |

---

## booking/

End-to-end SOPs for the email-to-calendar booking agent.

| File | Purpose |
|------|---------|
| `email_calendar_booking.md` | Full booking agent SOP — fetch threads, classify, propose slots, confirm, log |
| `email_booking_n8n.md` | Variant that routes the booking agent through an n8n webhook trigger |

---

## config/

JSON configuration files consumed by tools at runtime.

| File | Consumed by | Purpose |
|------|------------|---------|
| `n8n_webhooks.json` | `tools/n8n_api.py` | Maps human-readable identities to n8n webhook URLs |
| `n8n_webhook_workflow.json` | n8n import | Exportable n8n workflow definition for the webhook trigger flow |
