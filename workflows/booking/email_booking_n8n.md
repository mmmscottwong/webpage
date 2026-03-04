# Workflow: Email booking – Notify Local Agent

## Objective
Use a **remote n8n** instance to detect booking‑related Gmail messages and notify your **local booking agent** (this project on `d:\Agent`) via HTTP. The local agent then runs the Python booking tools to update `.tmp/` state and generate a draft reply.

This workflow assumes:
- n8n is already connected to Gmail (OAuth done inside n8n).
- Your local machine exposes an HTTPS endpoint (via Cloudflare Tunnel / ngrok / similar) that forwards to a small HTTP server in this repo at path `/bookings/email`.

## Required inputs

- **n8n (remote)**
  - Working n8n instance (cloud or self‑hosted).
  - A Gmail credential set up inside n8n (for the Gmail node).

- **Local machine (this repo)**
  - `d:\Agent` with all booking tools set up (Google auth, etc.).
  - A small HTTP server script (e.g. `py tools/booking_http_server.py`) exposing:
    - `POST /bookings/email`
  - An HTTPS tunnel or reverse proxy from a public URL down to this local server, e.g.:
    - `https://your-home-domain/bookings/email`

- **Shared secret**
  - Generate a random string and set it in your local environment, e.g.:
    ```env
    BOOKING_AGENT_SECRET=some-long-random-string
    BOOKING_AGENT_EMAIL=you@example.com
    ```
  - Configure the n8n HTTP Request node to send this value as header `X-AGENT-TOKEN`.

## Node overview (n8n)

- **Node 1 – Cron**: runs every 5–10 minutes during your business hours.
- **Node 2 – Gmail**: lists recent unread booking‑related emails.
- **Node 3 – HTTP Request**: POSTs each candidate email’s metadata to your local agent.
- **Node 4 – (Optional) Email / Telegram**: notifies you that the local agent was triggered.

You can later replace **Cron + Gmail** with a pure **Gmail Trigger** once you are happy with behaviour.

## Steps in n8n

### 1. Create workflow “Email Booking – Notify Local Agent”

1. In n8n UI, click **Workflows → New**.
2. Name it **Email Booking – Notify Local Agent**.

### 2. Add Cron node

1. Add a **Cron** node.
2. Configure:
   - Mode: **Every X minutes**.
   - Interval: e.g. **5 minutes**.
   - Add a **Time window** (optional) matching your business hours.

The Cron node will act as a sweep that checks for new booking emails regularly.

### 3. Add Gmail node (list candidate emails)

1. Add a **Gmail** node, connect it after **Cron**.
2. Operation: **Get Many** (List messages).
3. Resource: **Message**.
4. Filter:
   - Use a query like:
     - `is:unread label:booking`
     - or `is:unread subject:(booking OR consultation OR appointment)`
   - Adjust to your inbox structure (labels / aliases).
5. Limit: start with something small (e.g. **20**) to keep tests manageable.

This node outputs one item per matching email, with fields including `threadId`, `id`, `from`, `to`, `subject`, `snippet`.

### 4. Add HTTP Request node (call local agent)

1. Add an **HTTP Request** node, connect after **Gmail**.
2. Configure:
   - **Method**: `POST`
   - **URL**: your public tunnel URL, e.g.  
     `https://your-home-domain/bookings/email`
   - **Authentication**: None (you will use a shared secret header).
   - **Headers**:
     - `Content-Type`: `application/json`
     - `X-AGENT-TOKEN`: your `BOOKING_AGENT_SECRET` value.
   - **Body Content Type**: `JSON`.
   - **JSON/Body**:
     - Map key fields from the Gmail node, for example:
       - `threadId`: `{{$json["threadId"]}}`
       - `messageId`: `{{$json["id"]}}`
       - `from`: `{{$json["from"]}}`
       - `to`: `{{$json["to"]}}`
       - `subject`: `{{$json["subject"]}}`
       - `snippet`: `{{$json["snippet"]}}`
3. Response handling:
   - Expect a short JSON response from the local server:
     - e.g. `{ "ok": true, "threadId": "..." }`.
   - Set a reasonable timeout (e.g. 60 seconds).

Now, every item from the Gmail node will trigger a POST to your local booking agent.

### 5. Optional: notification node

1. Add an **IF** node after **HTTP Request**:
   - Condition: `Status Code` equals `200`.
2. On the “true” branch, add an **Email** node or another notifier:
   - Subject: `Email booking agent triggered`
   - Body: include the `threadId`, `subject`, and any fields you care about from the Gmail / HTTP response.

This makes it easy to see when the agent runs, especially while you are still testing.

## What the local agent should do

The local HTTP server (see separate endpoint design) should, when it receives `POST /bookings/email`:

1. Validate the `X-AGENT-TOKEN` header against `BOOKING_AGENT_SECRET`.
2. Extract `threadId` (and other optional metadata).
3. Run the booking tool chain for that thread:
   - `py tools/gmail_fetch_threads.py --thread-id <threadId>`
   - `py tools/analyze_email_for_booking.py --thread-id <threadId>`
   - `py tools/thread_state_manager.py --update-only`
   - `py tools/google_calendar_availability.py` (for up‑to‑date free slots)
   - `py tools/generate_time_proposals.py --thread-id <threadId>`
   - `py tools/draft_booking_email_reply.py --thread-id <threadId> --my-email %BOOKING_AGENT_EMAIL%`
4. Return quickly to n8n with a small JSON body indicating success or failure.

The actual implementation of this HTTP server lives in `tools/booking_http_server.py` (see local endpoint design).

## Optional callback workflow

Later, you can add a second workflow in n8n to receive callbacks from the local agent when drafts or confirmed bookings are ready:

- Create a workflow **“Booking Agent Callback”**.
- Add a **Webhook** node with path like `/booking-callback`.
- From your local agent, `POST` JSON payloads such as:
  ```json
  {
    "event": "draft_created",
    "threadId": "abc123",
    "summary": "Client asked for consultation next week",
    "proposedSlots": ["2026-03-10T10:00:00+08:00/2026-03-10T11:00:00+08:00"]
  }
  ```
- In the same workflow, add an **Email / Telegram / Slack** node to notify you with a human‑readable summary.

This keeps all sensitive Gmail/Calendar access and booking logic on your own machine, while n8n only orchestrates and notifies.

