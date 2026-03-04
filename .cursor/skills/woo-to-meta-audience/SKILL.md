---
name: woo-to-meta-audience
description: Exports WooCommerce contacts with optional date and product filters, then creates or updates a Meta Custom Audience from the email list. Use when the user asks to sync WooCommerce customers or purchasers to Meta audience, create audience from WooCommerce, export buyers to Facebook/Instagram ads, or filter by date range or product and send to Meta.
---

# WooCommerce Contacts to Meta Audience List

When the user wants to **build a Meta (Facebook/Instagram) Custom Audience from WooCommerce contacts** with optional **filtering by date range or product**, run the project tools from the **project root** in this order.

## When to Apply

- User says: sync WooCommerce to Meta audience, create audience from WooCommerce, export purchasers to Meta/Facebook/Instagram ads, WooCommerce contacts to audience list, or similar.
- User specifies filters: date range (e.g. "last week", "6/2–12/2"), product/SKU, or "everyone who purchased in …".

## 1. Export WooCommerce Contacts (with filtering)

**Tool:** `tools/woocommerce_api.py`

From project root. Ensure `.tmp` exists (e.g. `mkdir .tmp -Force`).

### Filter: Purchasers in date range (no product)

Unique customers with **completed or processing** orders between two dates:

```powershell
py tools/woocommerce_api.py --purchasers-between --from YYYY-MM-DD --to YYYY-MM-DD | Set-Content -Path .tmp/woo_purchasers.csv -Encoding UTF8
```

- Dates are **inclusive**; use Hong Kong time by default.
- Output CSV has a single column: `email`.

### Filter: Customers who bought a specific product in date range

```powershell
py tools/woocommerce_api.py --customers-for-product SKU_OR_NAME --from YYYY-MM-DD --to YYYY-MM-DD | Set-Content -Path .tmp/woo_product_customers.csv -Encoding UTF8
```

- `--customers-for-product`: product **SKU** or use with `--report-product "Product Name"` for name substring.
- Output CSV has columns: `email`, `first_name`, `last_name`, `order_id`, `order_date`, `total`, `product_name`, `quantity`. Meta step uses the `email` column.

If the user does not specify a product, use **purchasers-between**. If they specify a product or SKU, use **customers-for-product**.

## 2. Create or Update Meta Custom Audience

**Tool:** `tools/meta_audiences_api.py`

**Prereqs:** `.env` must have `META_SYSTEM_USER_TOKEN` (with `ads_management` and access to the Ad account) and `META_AD_ACCOUNT_ID` (e.g. `act_114873052382192`). See `workflows/meta_audience_create.md` if permissions errors occur.

### Audience naming convention

Use this format for **online store purchaser** audiences (date-range, no product filter):

- **`Static_OnlineStore_Purchasers_YYYYMMDD-YYYYMMDD`**  
  Example: `Static_OnlineStore_Purchasers_20260206-20260212` for purchasers 6 Feb–12 Feb 2026.

For **product-specific** audiences, use a short label and date range, e.g. `Static_ProductX_Buyers_YYYYMMDD-YYYYMMDD`.

### Create new audience and upload the list

```powershell
py tools/meta_audiences_api.py create --name "Audience_Name" [--description "Optional"] --csv .tmp/woo_purchasers.csv --email-column email
```

- Use the **naming convention** above (e.g. `Static_OnlineStore_Purchasers_20260206-20260212`).
- CSV path is the file from step 1. Column is `email` for purchasers-between; `email` for customers-for-product output as well.
- Script creates the audience, then uploads hashed emails in batches (max 10k per request). Processing can take up to 24 hours on Meta’s side.

### Add to an existing audience

If the audience already exists and the user wants to add more people:

```powershell
py tools/meta_audiences_api.py add-users --audience-id <NUMERIC_ID> --csv .tmp/woo_purchasers.csv --email-column email
```

- Get existing audience IDs with: `py tools/meta_audiences_api.py list`.

### Rename an existing audience

```powershell
py tools/meta_audiences_api.py rename --audience-id <NUMERIC_ID> --name "Static_OnlineStore_Purchasers_YYYYMMDD-YYYYMMDD"
```

## 3. Report Back

- Print the **audience ID** and that the list can be used in **Ads Manager** for targeting.
- If the user asked for the list in Drive or email, follow the **deliver-to-drive-and-email** skill after saving the CSV (step 1 output is already in `.tmp/`).

## Quick Reference

| Filter              | WooCommerce command                                                                 | CSV column |
|---------------------|--------------------------------------------------------------------------------------|------------|
| Date range only     | `--purchasers-between --from YYYY-MM-DD --to YYYY-MM-DD`                             | `email`    |
| Product + date      | `--customers-for-product SKU --from YYYY-MM-DD --to YYYY-MM-DD` [+ `--report-product "Name"`] | `email`    |
| Create audience     | `meta_audiences_api.py create --name "..." --csv <path> --email-column email`        | —          |
| Add to audience     | `meta_audiences_api.py add-users --audience-id <ID> --csv <path> --email-column email`| —          |
| Rename audience     | `meta_audiences_api.py rename --audience-id <ID> --name "Static_OnlineStore_Purchasers_YYYYMMDD-YYYYMMDD"` | —          |

## Errors

- **WooCommerce 403:** API key may lack Read orders; check WooCommerce → Settings → Advanced → REST API.
- **Meta 400 Permissions:** Token needs `ads_management` and the identity (user or System User) must have the Ad account assigned in Business Settings. See workflow doc.
- **Column 'email' not found:** CSV may have UTF-8 BOM; the tool reads with `utf-8-sig`. If the column has another name, use `--email-column "ColumnName"`.
