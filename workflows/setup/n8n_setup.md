# Workflow: Connect N8N

## Objective
Enable the project to call your n8n instance’s REST API: list workflows, list executions, and trigger workflows via webhook URL.

**Note:** The n8n REST API is not available on the free trial; you need a paid/self‑hosted instance.

## Required inputs
- **n8n instance URL** — base URL (e.g. `https://n8n.pipucapyonline.com` or `http://localhost:5678`), no trailing slash.
- **API key** — from n8n **Settings → n8n API** → Create API key. Sent as header `X-N8N-API-KEY`.

## Tools to use
- `tools/n8n_api.py` — list workflows, list executions, trigger a workflow by webhook URL. Uses `N8N_BASE_URL` and `N8N_API_KEY` from `.env`.

## Steps

### 1. Create an API key in n8n
1. Log in to n8n → **Settings** (gear) → **n8n API**.
2. **Create an API key** — set a label and expiration.
3. Copy the key and add it to `.env` as `N8N_API_KEY`. It is shown only once.

### 2. Add to `.env`
```env
N8N_BASE_URL=https://your-n8n-instance.com
N8N_API_KEY=your-api-key
```

If n8n is under a path (e.g. `https://example.com/n8n`), set `N8N_BASE_URL=https://example.com/n8n`.

### 3. Verify
From project root (Windows Terminal):

```powershell
py tools/n8n_api.py --workflows
py tools/n8n_api.py --executions -n 5
```

### 4. 開一個有 Webhook trigger 嘅 workflow（二揀一）

**方法 A：用 API 自動建立**（要 n8n REST API 可用）：

```powershell
py tools/n8n_api.py --create-webhook-workflow
```

會建立一個名為「Agent Webhook Trigger」嘅 workflow，webhook path 係 `agent-trigger`。建立後去 n8n 介面搵呢個 workflow → 按 **Activate**，就會得到 URL：`{N8N_BASE_URL}/webhook/agent-trigger`。

**方法 B：人手匯入 JSON**

1. 打開 `workflows/n8n_webhook_workflow.json`（入面已有一個 Webhook + Respond to Webhook 嘅 workflow）。
2. 喺 n8n：左上 **Workflows** → 三點選單 → **Import from File**（或 **Import from URL**），揀呢個 JSON 檔。
3. 匯入後喺編輯器按 **Save**，再按 **Activate**。
4. 啟用後，Webhook 節點會顯示 Production URL，例如：`https://你的n8n網址/webhook/agent-trigger`。

### 5. Trigger a workflow (webhook)
To run a workflow from the tool, the workflow must have a **Webhook** trigger node. After saving and activating, n8n shows the webhook URL (e.g. `https://your-n8n.com/webhook/agent-trigger`).

```powershell
py tools/n8n_api.py --trigger "https://your-n8n.com/webhook/agent-trigger"
```

Optional: send JSON body (tool accepts `--data '{"key":"value"}'`).

### 6. Webhook 登記表（用 identity 畀 Cursor / tools 調用）

專案入面有一個 **table**：`workflows/n8n_webhooks.json`。每個 n8n webhook 用一個 **identity**（名）對應一條 full URL，咁 Cursor 或其他 tool 就可以用名嚟 trigger，唔使記 URL。

- **睇已登記嘅 identity**：`py tools/n8n_api.py --list-webhooks`
- **用 identity trigger**：`py tools/n8n_api.py --trigger-by-name agent-trigger`（可加 `--data '{"key":"value"}'`）
- **加新 webhook**：開 `workflows/n8n_webhooks.json`，加一行 `"identity名": "https://n8n.../webhook/path"`，例如 `"sales-report": "https://n8n.pipucapyonline.com/webhook/sales-report"`。之後就可以 `--trigger-by-name sales-report`。

### 7. 用 Agent 幫手修改 / 優化 n8n workflow

可以用 Cursor（Agent）經 API **拎** 同 **更新** workflow，做到修改或優化（加 node、改設定等）。

**步驟：**

1. **拎 workflow ID**：`py tools/n8n_api.py --workflows` 會列出 id 同 name。
2. **導出完整 JSON**：  
   `py tools/n8n_api.py --get-workflow <ID> > .tmp/workflow_<id>.json`  
   會把該 workflow 嘅完整定義（nodes、connections、settings）輸出到檔案。
3. **改 JSON**：你或 Agent 改 `.tmp/workflow_<id>.json`（加 node、改 parameters、改 connections 等）。n8n API 只支援 **全量更新**（PUT），所以要保留原有嘅 name、nodes、connections、settings，只改要改嘅部分。
4. **寫回 n8n**：  
   `py tools/n8n_api.py --update-workflow <ID> --file .tmp/workflow_<id>.json`  
   會用改好嘅 JSON 覆蓋該 workflow。
5. 喺 n8n 介面檢查結果，必要時 **Unpublish → Publish** 一次（尤其有 Webhook 時）。

**Agent 可以幫你：**

- 加 node（例如 Webhook 後面加「Respond to Webhook」、加 Delay、加 IF 等）  
- 改 node 嘅 parameters（例如 webhook path、timeout）  
- 改 connections（邊個連去邊個）  
- 優化設定（settings）  

你話「幫我優化 Agent Webhook Trigger」或「喺 workflow X 加一個 Delay 3 秒」，Agent 可以拎該 workflow JSON，改好，再幫你 run `--update-workflow`。

## Expected outputs
- `--workflows` lists workflows (id, name, active).
- `--executions` lists recent executions (id, workflow, status, start time).
- `--trigger <url>` returns the webhook response (e.g. 200 and workflow output).

## Edge cases / notes
- **API not available**: If you see 404 or “API not available”, your plan may not include the REST API (e.g. free trial). Use webhook trigger instead.
- **Self‑hosted path**: If n8n runs at `http://host:5678` with no path, use `N8N_BASE_URL=http://host:5678`. If it’s at `https://domain.com/n8n`, use `N8N_BASE_URL=https://domain.com/n8n`.
- **Webhook auth**: Production webhooks can use header auth or query params; configure in the Webhook node. This tool sends a plain POST; add headers in the script if your webhook requires them.
- **Rate limits**: Respect n8n rate limits; avoid very large `-n` or rapid repeated calls.

---

## "The requested webhook … is not registered"（self-hosted Docker）

若你收到 n8n 嘅 JSON 404（`"The requested webhook \"POST agent-trigger\" is not registered"`），即係請求已到 n8n，唔係 Cloudflare 擋，而係 **n8n 入面未註冊到呢個 webhook**。

### 常見原因（Docker self-host）

1. **Queue mode（多個 container）**  
   有 **main**（接 webhook）同 **worker**（做 execution）。Webhook 只會註冊喺 main。若 request 被指去 worker 或另一隻 instance，就會 404。  
   **做法**：確保 webhook 流量去 **main** container（reverse proxy 只對 main 轉發 `/webhook`），或暫時改做 single instance 試。

2. **Restart / 重新 deploy 後未 re-register**  
   關 container 或更新 image 後，有時 UI 顯示 Published 但 webhook 未再註冊。  
   **做法**：喺 n8n **Editor** 開該 workflow → 關 **Published**（Unpublish）→ 再開返 **Published**，然後再試 trigger。

3. **確認係同一個 workflow**  
   確認你 Publish 緊嘅係「Agent Webhook Trigger」且 path 係 `agent-trigger`。用 `py tools/n8n_api.py --webhook-urls` 對 URL 同 active。

### Cloudflare 點樣改（令 webhook 唔使登入）

若 n8n 前面有 **Cloudflare Access**，未登入嘅請求會彈登入頁或 404。要令 Agent / 外部系統可以 call webhook，就要喺 Cloudflare 放行 `/webhook`。

**方法：為 webhook path 開一個獨立 Application，用 Bypass**

1. **登入 Cloudflare Zero Trust**  
   https://one.dash.cloudflare.com → 揀你個 account（例如 pipucapyonline）。

2. **Access → Applications → Add an application**  
   - **Application type**：Self-hosted（或你現有嘅類型）。  
   - **Application name**：例如 `n8n Webhook Bypass`。  
   - **Session duration**：隨意（Bypass 唔會用嚟登入）。

3. **Public hostname（緊要）**  
   - **Subdomain**：`n8n`（同你 n8n 嘅 subdomain 一樣）。  
   - **Domain**：`pipucapyonline.com`（你嘅 domain）。  
   - **Path**：填 `webhook` 或 `webhook/`。  
   - 即係呢個 Application 只處理：`n8n.pipucapyonline.com/webhook` 同下面嘅 path（例如 `/webhook/agent-trigger`）。

4. **Access policies**  
   - 撳 **Create new policy**（或 Select existing）。  
   - **Policy name**：例如 `Bypass`。  
   - **Action**：揀 **Bypass**。  
   - **Include**：Selector 揀 **Everyone**（即係所有人，唔使登入）。  
   - 儲存。

5. **Application 次序**  
   - 若你有多個 Application 都包 `n8n.pipucapyonline.com`（例如「n8n Dashboard」要登入 + 「n8n Webhook Bypass」），要確保 **path 較具體嘅先計**。  
   - 通常「n8n Webhook Bypass」有 path `webhook/`，會只 match `/webhook/*`；「n8n Dashboard」冇 path 或 path 唔同，就 match 其餘。  
   - 唔好兩個 Application 用同一個 hostname + 同一個 path，否則會亂。

6. **改完之後**  
   - 用 `py tools/n8n_api.py --trigger-test "https://n8n.pipucapyonline.com/webhook/agent-trigger"` 試。  
   - 若回 **JSON**（包括 n8n 嘅 "not registered"）＝Cloudflare 已放行，請求到咗 n8n。  
   - 若回 **HTML 登入頁**＝仍被 Access 擋，要再對一次 Application 嘅 hostname + path 同 policy（Bypass + Everyone）。

**注意**：Cloudflare 只負責「放唔放行」同指去你嘅 origin（一組 IP 或 Tunnel）。**/webhook 入到去之後指去 main 定 worker**，係你 server 上面 reverse proxy（Nginx / Traefik 等）做，唔係 Cloudflare 設定。即係「點樣改 Cloudflare」＝改 Access 放行 webhook；「點樣改 main/worker」＝改 Nginx 等。

---

### 點樣確保 /webhook 流量去 main container（queue mode）

Queue mode 下：**main** 負責接 webhook / UI / API，**worker** 只係拎 Redis 嘅 job 嚟跑。若 reverse proxy 把請求分去 worker，webhook 就會 404。

**0. 點樣搵 server config（Nginx / Traefik 喺邊）**

你要喺 **行 n8n 嗰部 server**（Linux）用 SSH 登入，或喺 host 機用 terminal。

- **唔知用緊 Nginx 定 Traefik？**  
  - 睇有冇 **docker-compose**：`docker compose config` 或打開 `docker-compose.yml`，睇有冇 service 叫 `nginx`、`traefik`、`caddy`、`cloudflared`。  
  - 或睇有咩 listen 80/443：`sudo ss -tlnp | grep -E ':80|:443'`（或 `sudo netstat -tlnp`），睇係邊個 process（nginx、traefik 等）。

- **Nginx 常見 config 位置**：  
  - `/etc/nginx/nginx.conf`（主 config，入面會有 `include` 其他）  
  - `/etc/nginx/sites-enabled/`、`/etc/nginx/conf.d/`（逐個 site 嘅 config）  
  - 搜 n8n 或 domain：`sudo grep -r "n8n\|5678\|pipucapyonline" /etc/nginx/`

- **Traefik**：  
  - 若用 Docker：config 多數喺 **compose 入面 labels** 或 **volume 掛入去嘅 yml**。  
  - 睇 n8n 同 traefik 嘅 compose：`docker compose config` 或打開你 deploy n8n 嗰個 folder 嘅 `docker-compose.yml`。

- **Cloudflare Tunnel（cloudflared）**：  
  - config 多數係 `config.yml` 或 `~/.cloudflared/config.yml`，入面 `ingress` 會寫指去邊個 host:port。

搵到邊個做 reverse proxy 之後，再跟下面「Nginx 點改」或「Traefik 點改」改。

---

**1. 確認係咪 queue mode**

- 睇 `docker-compose.yml`（或 k8s）：有冇多個 n8n service（例如 `n8n`、`n8n-worker`）同 Redis。
- 若只有一隻 n8n container、冇 Redis，通常係 single instance，唔使搞 routing。

**2. 認住邊個係 main**

- 一般 main 係唔帶 `EXECUTIONS_MODE=queue` 做 worker 嘅嗰隻，或者名就係 `n8n` / `n8n-main`。
- 喺 compose 入面，main 多數**冇** `N8N_CONTAINER_TYPE=worker` 或類似設定；worker 先會有。

**3. 改 reverse proxy：全部流量（或至少 /webhook、/）指去 main**

下面係 **Nginx** 同 **Traefik** 嘅具體改法。改完 **重啟 proxy**，再喺 n8n 做 **Unpublish → Publish**。

---

#### Nginx 點改

**唔好咁做**（會令 webhook 有時去咗 worker，404）：
```nginx
upstream n8n {
    server n8n:5678;
    server n8n-worker:5678;   # ❌ 唔好加 worker 落去
}
```

**正確**：只指去 main 一隻。
```nginx
# 只寫 main container 嘅名同 port（compose 入面 main 多數叫 n8n）
upstream n8n_main {
    server n8n:5678;
}

server {
    listen 80;
    server_name n8n.pipucapyonline.com;

    location / {
        proxy_pass http://n8n_main;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- 若你而家 `upstream` 入面有 **多過一個** `server`（例如 main + worker），**刪走 worker**，只留 main 嗰行。  
- 改完：`sudo nginx -t` 檢查，再 `sudo systemctl reload nginx`（或你嘅重啟方式）。

---

#### Traefik 點改

**唔好**：同一個 Router 嘅 Service 指去多個 server（main + worker load balance）。  
**正確**：對外嘅 Router 只指去 **main** 呢個 Service，worker **唔好** 掛任何對外 label。

**Docker Compose 示例**（只 main 對外，worker 唔對外）：

```yaml
services:
  n8n:
    image: n8nio/n8n
    # ... 你嘅 env、volumes
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.pipucapyonline.com`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
    # 唔好同 n8n-worker 共用同一個 traefik router / service

  n8n-worker:
    image: n8nio/n8n
    # ... queue mode env、Redis 等
    # ❌ 唔好加 traefik.http.routers... 等對外 label，worker 唔應該從外網入
```

若你用 **Traefik 靜態 config / 檔案**：  
- 只開一個 Service，backend 只寫 main 嘅 URL（例如 `http://n8n:5678`）。  
- 唔好為 worker 開對外 Router，或唔好把 worker 加落同一個 Service 嘅 backend。

改完：重啟 Traefik 同相關 container。

---

#### Caddy / Cloudflare Tunnel

- **Caddy**：`reverse_proxy` 只寫 main 一個 address，例如 `reverse_proxy n8n:5678`，唔好寫多個。  
- **Cloudflare Tunnel**：`config.yml` 入面 `ingress` 指去嘅 origin 只係 main（例如 `http://n8n:5678`），唔好指去 worker。

**若你只得一隻 n8n + cloudflared（冇 Nginx/Traefik）**：  
即係 **single instance**，所有流量已經去嗰一隻 n8n，唔使改 proxy。webhook 404 多數係未 re-register：做 **Unpublish → Publish**，必要時重啟 n8n container 一次（`docker compose restart n8n`）。

**若做完 Unpublish → Publish 同 restart 都仲係 404**，可試：  
- 喺 n8n 開該 workflow → 編輯 Webhook 節點 → 把 **Path** 改成新嘅（例如 `agent-trigger-v2`）→ Save → Publish，再用新 URL 試（`/webhook/agent-trigger-v2`）。  
- 或 **複製** 成個 workflow（新名）→ 刪走舊嘅 → 開新嘅 → Publish，再試。  
- 睇 container log 有冇錯：`docker logs n8n-local 2>&1 | tail -50`。

**4. 改完之後**

- 重啟 proxy 同（如有需要）main container。
- 喺 n8n 再 Unpublish → Publish 一次 webhook workflow。
- 用 `py tools/n8n_api.py --trigger-test "https://n8n.../webhook/agent-trigger"` 再試。

**5. 若唔肯定邊隻係 main**

- 睇官方/compose 嘅 queue mode 範例：通常「冇設成 worker 嘅 n8n」就係 main。  
- 或暫時關咗 worker，只留 main + Redis，試下 webhook 係咪正常；正常就代表之前係 routing 去錯 instance。

### 點睇 deployment 同 log（Docker）

- **Single vs multi-node**：睇你點 run。一隻 container 通常係 single。若有 `queue` / `worker` / Redis 就係 queue mode，要睇邊個係 main、webhook 指去邊。
- **Log**：`docker logs <n8n-container-name>` 或 `docker compose logs n8n`。睇有冇 webhook 註冊或 404。介面 **Executions** tab 睇有冇 execution。
- **Test**：`py tools/n8n_api.py --trigger-test "https://n8n.../webhook/agent-trigger"` — 若 response 係 n8n JSON（"not registered"）＝已到 n8n；若係 HTML ＝仍被 Cloudflare 擋。
