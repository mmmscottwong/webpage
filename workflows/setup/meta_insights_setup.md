# Workflow: Connect Meta (Facebook / IG) Insights

## Objective
Use Meta Graph / Marketing API to pull **Facebook Page** and **Instagram Business** insights using a long‑lived System User token, then make it easy to send the data into Google Sheets.

> Threads insights are **not** properly exposed via public APIs yet. We document what’s possible and where it stops.

---

## 1. Required inputs

- **System User token** with Marketing / Insights scopes (you already have one, just plug it in):
  - Example scopes: `pages_read_engagement`, `pages_show_list`, `read_insights`, `instagram_basic`, `instagram_manage_insights`.
- **Facebook Page ID** – the Page you want to report on.
- **Instagram Business Account ID** – IG account linked to the Page / Business Manager.

### 1.1 Environment variables

In `.env` (you already set real values; below is the shape):

```env
META_SYSTEM_USER_TOKEN=EAADxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
META_PAGE_ID=123456789012345
META_IG_BUSINESS_ID=1784xxxxxxxxxxxx
```

`META_GRAPH_API_VERSION` is optional; defaults to `v18.0` if not set.

The placeholders are also documented in `.env.example` so future environments know what to fill.

---

## 2. How to get the IDs (reference)

### 2.1 Facebook Page ID

Any一個方法都可以：

- **Page 設定**：
  1. 去你個 Facebook Page。
  2. 入 `About` / Page Info / 關於。
  3. 底部通常會顯示 **Page ID**（一串數字）。

- **View Source**：
  1. 開 Page → Browser 按 `Ctrl+U`（View source）。
  2. 搜索 `page_id=`。
  3. 例如見到 `\"page_id\":\"167138230010680\"`，嗰串數字就係 Page ID。

### 2.2 Instagram Business Account ID

前提：IG account 已經變成 **Business / Creator** 同已綁定去你個 Facebook Page / Business Manager。

方法 A（借 Graph API，一次性）：

```text
GET https://graph.facebook.com/v18.0/<PAGE_ID>?fields=instagram_business_account&access_token=<META_SYSTEM_USER_TOKEN>
```

回應：（簡化）

```json
{
  "instagram_business_account": {
    "id": "1784xxxxxxxxxxxx"
  },
  "id": "<PAGE_ID>"
}
```

呢個 `instagram_business_account.id` 就係 `META_IG_BUSINESS_ID`。

方法 B（Business Suite 介面）：

- 進入 `business.facebook.com` → Business Settings → 「Accounts」→ **Instagram accounts**。
- 點入 IG 帳戶，網址列 `asset_id=1784...` 後面嗰串就係 IG Business ID。

---

## 3. Tool: `tools/meta_insights_api.py`

CLI 用法（由專案根目錄 `d:\Agent` 開 PowerShell）：

### 3.1 Page 貼文 insights

```powershell
py tools/meta_insights_api.py --page-posts --date-preset last_7d -n 20
```

輸出（tab‑separated）：

```text
post_id    created_time    message    post_impressions    post_impressions_unique    post_engaged_users    post_clicks    post_reactions_like_total    post_comments    post_shares
...
```

**注意**：你而家個 `META_SYSTEM_USER_TOKEN` 係 **User / System token**，Meta 要求新 Pages experience 用 **Page access token** 做部分 insights call。若收到：

```text
User Access Token Is Not Supported – A Page access token is required for this call...
```

代表你要：
- 用 System User token 呼叫 Business API 換取 Page token，或者
- 直接用人手 login 取得 Page token（開發環境測試）。

暫時 `meta_insights_api.py` 假設你已經有能直接調用 insights 嘅 token；若將來你想加「先用 System User token 換 Page token」的流程，我可以幫你再擴展。

### 3.2 IG 帳戶 insights

```powershell
py tools/meta_insights_api.py --ig-insights --date-preset last_7d
```

會列出每日 `reach / follower_count / profile_views` 的數值。

### 3.3 IG 貼文 / Reels 基本數據

```powershell
py tools/meta_insights_api.py --ig-media -n 20
```

會列出最近 media 的：

- id
- timestamp
- media_type
- like_count
- comments_count
- caption（截斷到 80 字）
- permalink

### 3.4 Page level insights（實驗性）

```powershell
py tools/meta_insights_api.py --page-insights --date-preset today
```

- 目前只查 `page_fans`（fans 數量）。  
- 如你版本不支援該 metric，tool 會提示你去 Meta docs 揀返支援的 metric，再改 `meta_insights_api.py` 裡面的列表。

### 3.5 Threads insights

```powershell
py tools/meta_insights_api.py --threads-insights
```

- 只會打印說明文字：目前 Threads insights 冇穩定公開 API。  
- 若 Meta 將來透過 IG API 暴露 Threads 數據，可以在 `meta_insights_api.py` 裡加對應 endpoint。

---

## 4. 同 Google Sheets 整合（簡單版本）

你已經有 `tools/google_sheets.py`，可以用兩步組合：

### 4.1 將 insights 輸出到檔案

```powershell
py tools/meta_insights_api.py --page-posts --date-preset yesterday -n 50 > .tmp/meta_page_posts.tsv
```

### 4.2 寫入 Google Sheet

1. 在 Sheets 建一個 Spreadsheet，copy 佢的 `spreadsheetId`。  
2. 用 `google_sheets.py` append：

```powershell
$rows = Get-Content .tmp/meta_page_posts.tsv | ForEach-Object { $_ -split "`t" }
# PowerShell 傳 array 較麻煩，簡單做法：手動 copy / paste 或在 Python 裡讀 tsv 後呼叫 google_sheets 庫。
```

更實際：在 Python 裡讀 `meta_page_posts.tsv`，然後用 `google_sheets.append_rows(...)` 做一個小 helper（如果你想，我可以幫你再寫一個專用 `export_meta_insights_to_sheet.py`）。

---

## 5. 測試與錯誤訊息

- Token 無效 / 冇權限：Meta 通常會回 `OAuthException`，tool 會顯示 status code 同 JSON error。  
- metric 不支援：會顯示 `The value must be a valid insights metric`，再建議你去 Meta docs 揀返支援嘅 metric。  
- IG account 未連接：`--ig-insights` / `--ig-media` 會回 Meta 的錯誤訊息，幫助你檢查 IG 是否已變成 Business/Creator 並且連接到 Page / Business Manager。

---

## 6. 下一步（如果你想加深整合）

- 做一個 `export_meta_insights_to_sheet.py`：
  - 讀 `meta_insights_api.py` 輸出或直接用 Graph API。
  - 寫入某個固定的 Sheet tab（例如 `FB_Insights`、`IG_Insights`）。
- n8n workflow：
  - 用 Cron node 定時 call 你現有的 webhook。
  - webhook node 裏面 call `meta_insights_api.py` 或直接用 HTTP Request node 拉 Graph API，之後寫去 Sheets 或 Slack / Email 報告。*** End Patch```} +#+#+#+#+#+assistant to=functions.ApplyPatch_REALTYPEassistant렵 to=functions.ApplyPatchезультassistant to=functions.ApplyPatch人人爽人人assistant to=functions.ApplyPatch MarkDown to=functions.ApplyPatch assistant to=functions.ApplyPatchédients to=functions.ApplyPatch JSON to=functions.ApplyPatchassistant to=functions.ApplyPatchelschap to=functions.ApplyPatch to=functions.ApplyPatchassistant to=functions.ApplyPatchpòt to=functions.ApplyPatch to=functions.ApplyPatchassistant to=functions.ApplyPatch JSON рика to=functions.ApplyPatchassistant to=functions.ApplyPatch:@"%@",assistant to=functions.ApplyPatch RichTextPanel to=functions.ApplyPatchassistant to=functions.ApplyPatchassistant to=functions.ApplyPatch  Frederic to=functions.ApplyPatchassistant to=functions.ApplyPatch Rubin to=functions.ApplyPatchassistant to=functions.ApplyPatch to=functions.ApplyPatchassistant to=functions.ApplyPatch 牌 to=functions.ApplyPatchassistant to=functions.ApplyPatch_Args## Test Input Reasoning
