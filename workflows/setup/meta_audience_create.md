# Meta Custom Audience – Setup & Usage

## Objective
Create a Custom Audience in Meta Ads Manager from a CSV of customer emails, then use it for ad targeting or suppression.

## Prerequisites
- Meta Business Suite account with an Ad Account
- System User token with `ads_management` scope (same token as `meta_insights_setup.md`)
- Ad Account ID from Ads Manager → Account Settings (format: `act_123456789`)

## Required .env Variables
```
META_SYSTEM_USER_TOKEN=...        # System User token (ads_management scope)
META_AD_ACCOUNT_ID=act_123456789  # From Ads Manager → Account Settings
META_GRAPH_API_VERSION=v19.0      # Optional, defaults to v19.0
```

## Tool
`tools/meta_audiences_api.py`

## Commands

**List existing Custom Audiences:**
```powershell
py tools/meta_audiences_api.py list
```

**Create an empty audience:**
```powershell
py tools/meta_audiences_api.py create --name "My Audience" --description "Optional description"
```

**Create audience and upload emails from CSV in one step:**
```powershell
py tools/meta_audiences_api.py create --name "My Audience" --csv path/to/customers.csv --email-column email
```

- Emails are normalized (lowercased, trimmed) and SHA-256 hashed before upload — raw emails never leave the machine
- Uploads in batches of 10,000 (Meta API limit)
- If the CSV column name is not `email`, specify it with `--email-column`

## CSV Format
The CSV must have a header row. Example:
```
email,name,phone
customer@example.com,John,+85291234567
```

## Notes
- `META_AD_ACCOUNT_ID` can be provided with or without the `act_` prefix — the tool normalizes it
- Token must have `ads_management` scope; `business_management` may also be required depending on account configuration
- After upload, audience size shows as estimated in Ads Manager (Meta processes the match asynchronously)
- Custom Audiences of type `CUSTOM` with source `USER_PROVIDED_ONLY` are used for direct customer file targeting
