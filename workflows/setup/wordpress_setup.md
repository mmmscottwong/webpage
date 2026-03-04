# Workflow: Connect WordPress / WooCommerce (ecommerce store)

## Objective
Enable the project to call your WordPress site’s REST API (posts, pages, site info) and WooCommerce’s API (products, orders) for your ecommerce store.

## Required inputs
- **WordPress site URL** — base URL of the store (e.g. `https://main.mimingmart.com`), no trailing slash.
- **WordPress Application Password** — for WP REST API (posts, pages). Created in the WordPress admin.
- **WooCommerce API keys** (optional) — for products, orders. Created under WooCommerce → Settings → Advanced → REST API.

## Tools to use
- `tools/wordpress_api.py` — WordPress REST API (posts, pages, site info). Uses Application Password from `.env`.
- `tools/woocommerce_api.py` — WooCommerce REST API: products, orders, **product updates**, **stock check / set / adjust**, **sales reporting**. Uses consumer key/secret from `.env`.

## Steps

### 1. Add credentials to `.env`
Copy from `.env.example` and set:

```env
# WordPress (required for wordpress_api.py)
WORDPRESS_URL=https://your-store.com
WORDPRESS_USER=your_admin_username
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx

# WooCommerce (required for woocommerce_api.py – products, orders)
WOOCOMMERCE_CONSUMER_KEY=ck_xxxxxxxxxxxx
WOOCOMMERCE_CONSUMER_SECRET=cs_xxxxxxxxxxxx
```

Use the same `WORDPRESS_URL` for both; WooCommerce runs on the same site.

### 2. Create a WordPress Application Password
1. Log in to WordPress admin → **Users** → **Profile** (your user).
2. Scroll to **Application Passwords**.
3. Enter a name (e.g. `Agent`) → **Add New Application Password**.
4. Copy the 24-character password (spaces optional) into `.env` as `WORDPRESS_APP_PASSWORD`.

Requires WordPress 5.6+ and HTTPS.

### 3. Create WooCommerce API keys (for products/orders)
1. WordPress admin → **WooCommerce** → **Settings** → **Advanced** → **REST API**.
2. **Add key** — description (e.g. `Agent`), user with admin/shop manager, **Read/Write**.
3. Copy **Consumer key** and **Consumer secret** into `.env` as `WOOCOMMERCE_CONSUMER_KEY` and `WOOCOMMERCE_CONSUMER_SECRET`. They are shown only once.

### 4. Verify
From project root (Windows Terminal):

```powershell
py tools/wordpress_api.py --site-info
py tools/woocommerce_api.py --products -n 3
```

### 5. WooCommerce: product updates, stock, reporting
- **Check one product (stock, price):** `py tools/woocommerce_api.py --product 278466`
- **List stock:** `py tools/woocommerce_api.py --stock -n 20`
- **Update product:** `py tools/woocommerce_api.py --update-product 278466 --set-stock 50` or `--set-price 99` or `--set-name "New name"`
- **Adjust stock (+/-):** `py tools/woocommerce_api.py --adjust-stock 278466 5` (add 5) or `--adjust-stock 278466 -3` (subtract 3)
- **Sales today (by product name):** `py tools/woocommerce_api.py --sales-today "CERM Hair"`
- **Sales in date range:** `py tools/woocommerce_api.py --sales-report --from 2026-03-01 --to 2026-03-03` (optional: `--report-product "CERM"`)

## Expected outputs
- `wordpress_api.py --site-info` prints site name and URL.
- `wordpress_api.py --posts` lists recent posts.
- `woocommerce_api.py --products` lists products; `--orders` lists orders (if keys have permission).

## Edge cases / notes
- **HTTPS**: Application Passwords and WooCommerce API require HTTPS.
- **Same URL**: Use one `WORDPRESS_URL` for both tools; WooCommerce uses `{WORDPRESS_URL}/wp-json/wc/v3`.
- **403 / 401**: Check username, Application Password (no typos, revoke and recreate if needed). For WooCommerce, regenerate keys and update `.env`.
- **CORS / blocked**: API must be reachable from your machine; if the store blocks non-browser requests, that must be relaxed on the server.
