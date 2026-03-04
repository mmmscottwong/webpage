# Workflow: Email calendar booking agent

## Objective
Use Gmail and Google Calendar to semi‑automate booking requests that arrive by email:
- Detect booking‑related Gmail threads.
- Analyse the conversation and extract booking intent + constraints.
- Check Google Calendar availability and propose time options.
- Draft reply emails for you to review/approve.
- Once confirmed, create a calendar event and send a confirmation email.

This workflow keeps per‑thread state in `.tmp/` so the agent remembers what has already been proposed or confirmed.

## Required inputs
- **Google setup completed**  
  - `credentials.json` and `token.json` exist in the project root.  
  - You have followed `[workflows/google_setup.md](workflows/google_setup.md)` and can run:
    - `py tools/google_gmail.py --list`
    - `py tools/google_calendar.py --calendars`

- **Booking configuration (in `.env`)**  
  Add entries like:
  ```env
  # Booking agent config
  BOOKING_CALENDAR_ID=primary                # Or a specific calendar ID
  BOOKING_TIMEZONE=Asia/Hong_Kong            # IANA time zone
  BOOKING_WORKING_HOURS=09:00-18:00          # Daily working window
  BOOKING_MEETING_LENGTH_MIN=60              # Default duration in minutes
  BOOKING_MIN_NOTICE_HOURS=24                # Do not offer slots sooner than this
  BOOKING_MAX_DAYS_AHEAD=14                  # How far ahead to propose slots
  BOOKING_PROPOSE_SLOTS=3                    # How many options to offer
  # Optional: log bookings to a Google Sheet
  # BOOKING_LOG_SHEET_ID=your_spreadsheet_id
  # BOOKING_LOG_SHEET_RANGE=Bookings!A:Z
  ```

- **n8n (optional but recommended for automation)**  
  - n8n instance reachable as described in `[workflows/n8n_setup.md](workflows/n8n_setup.md)`.
  - At least one workflow with a **Webhook** trigger that you can call from this project or external systems.

## Tools to use

Existing:
- `tools/google_auth.py` — shared OAuth for all Google APIs.
- `tools/google_gmail.py` — low‑level Gmail list/show/send helpers.
- `tools/google_calendar.py` — low‑level Calendar listing helpers.
- `tools/google_sheets.py` — optional logging of bookings to a Sheet.

New (booking‑specific):
- `tools/gmail_fetch_threads.py`  
  Fetch recent Gmail threads (IDs, headers, message bodies) that match a search query and write per‑thread JSON snapshots under `.tmp/email_threads/`.

- `tools/analyze_email_for_booking.py`  
  Use an LLM to classify each thread’s intent (`booking_new`, `reschedule`, `cancel`, `not_booking`) and extract structured booking details into `.tmp/email_analysis/THREAD_ID.json`.

- `tools/thread_state_manager.py`  
  Maintain per‑thread state in `.tmp/thread_state/THREAD_ID.json` (status, last proposed times, confirmed time, last processed message ID).

- `tools/google_calendar_availability.py`  
  Read the booking config from `.env`, query Google Calendar, and compute candidate free slots in JSON form.

- `tools/generate_time_proposals.py`  
  Combine the analysis output and calendar availability to pick a small set of human‑friendly time options for the guest.

- `tools/draft_booking_email_reply.py`  
  Use an LLM and the structured context (thread snapshot, analysis, state, proposals) to draft a reply email (subject + body). Save drafts under `.tmp/email_drafts/THREAD_ID_MESSAGE_ID.json`.

- `tools/create_calendar_event.py`  
  Given a chosen slot and thread metadata, create a Calendar event on the configured calendar and return the event details as JSON.

- `tools/send_gmail_message.py`  
  Send an email reply (plain text or HTML) using Gmail API. This can be used to send the final confirmation email once you approve a draft.

- `tools/log_bookings_to_google_sheet.py` (optional)  
  Append one row per booking to a configured Google Sheet (date, client, status, thread ID, event link, etc.).

## Steps

### 1. One‑time setup
1. **Complete Google auth**  
   - Follow `[workflows/google_setup.md](workflows/google_setup.md)`.  
   - Verify:
     ```powershell
     py tools/google_gmail.py --list -n 5
     py tools/google_calendar.py --calendars
     ```

2. **Configure booking options in `.env`**  
   - Add/adjust the `BOOKING_*` variables described above.  
   - Choose the calendar ID you want bookings to go into (e.g. `primary`).

3. **(Optional) Set up a logging Sheet**  
   - Create a spreadsheet (e.g. **Email Bookings Log**) with a sheet `Bookings`.  
   - Put a header row such as: `timestamp,threadId,client_name,client_email,status,requested,confirmed_start,confirmed_end,event_link`.  
   - Set `BOOKING_LOG_SHEET_ID` and `BOOKING_LOG_SHEET_RANGE` in `.env`.

### 2. Process new/updated Gmail threads

These steps can be orchestrated manually (run scripts from terminal) or via n8n calling a local runner / webhook that triggers these tools.

1. **Fetch candidate threads**  
   - Use `gmail_fetch_threads.py` with a query that targets booking emails, for example:
     ```powershell
     py tools/gmail_fetch_threads.py --query "has:userlabels booking OR subject:(booking OR consultation)" --max-threads 20
     ```
   - The script should:
     - Use Gmail API to list matching threads.
     - Fetch full thread details (messages, headers, plaintext bodies).
     - Write each thread snapshot to `.tmp/email_threads/THREAD_ID.json`.

2. **Analyse each thread for booking intent**  
   - Run:
     ```powershell
     py tools/analyze_email_for_booking.py --threads-dir .tmp/email_threads
     ```
   - For each `THREAD_ID.json`, the tool should:
     - Call your chosen LLM using environment variables for API keys.
     - Produce a JSON file: `.tmp/email_analysis/THREAD_ID.json` with fields like:
       - `intent`, `requested_time_windows`, `participants`, `duration_minutes`, `language`.

3. **Update per‑thread state**  
   - Run:
     ```powershell
     py tools/thread_state_manager.py --threads-dir .tmp/email_threads --analysis-dir .tmp/email_analysis
     ```
   - For each thread, the tool should:
     - Load existing state from `.tmp/thread_state/THREAD_ID.json` if present.
     - Decide new `status` (e.g. `new_request`, `times_proposed`, `confirmed`, `cancelled`).
     - Update `last_message_id`, `last_proposed_times`, `confirmed_time` as appropriate.

4. **Compute calendar availability and time proposals**  
   - First, get base availability:
     ```powershell
     py tools/google_calendar_availability.py --calendar-id primary --days-ahead 14
     ```
   - Then, for each thread that needs new proposals:
     ```powershell
     py tools/generate_time_proposals.py --thread-id THREAD_ID
     ```
   - These tools read `.env` booking config and the analysis/state JSON files, and write proposals to `.tmp/time_proposals/THREAD_ID.json`.

5. **Draft reply emails (semi‑automatic)**  
   - Run:
     ```powershell
     py tools/draft_booking_email_reply.py --thread-id THREAD_ID
     ```
   - The tool should:
     - Load the latest thread snapshot, analysis, state, and proposals.
     - Ask the LLM to draft a polite, on‑brand reply:
       - New booking: propose several concrete options.
       - Reschedule: reference the existing booking and propose alternatives.
       - Cancel: confirm cancellation and optionally suggest rescheduling.
     - Save a draft JSON: `.tmp/email_drafts/THREAD_ID_MESSAGE_ID.json` containing `subject`, `body_text`, `body_html`, `language`, `intent`.

6. **Review and approve drafts**  
   - Open the draft files in `.tmp/email_drafts/` and review the suggested text.  
   - Optionally, build a small local viewer or use n8n + Sheets to surface drafts for easy approval (see **Integration with n8n** below).

7. **Create calendar events and send confirmation**  
   - Once you decide on a time:
     ```powershell
     py tools/create_calendar_event.py --thread-id THREAD_ID --slot "2026-03-10T10:00:00+08:00" --duration 60
     ```
   - Then send an email using the approved draft:
     ```powershell
     py tools/send_gmail_message.py --thread-id THREAD_ID --use-latest-draft
     ```
   - Update the state and (optionally) log to Sheets:
     ```powershell
     py tools/thread_state_manager.py --threads-dir .tmp/email_threads --analysis-dir .tmp/email_analysis --update-only
     py tools/log_bookings_to_google_sheet.py --thread-id THREAD_ID
     ```

## Expected outputs
- JSON snapshots of each relevant Gmail thread under `.tmp/email_threads/THREAD_ID.json`.
- Structured analysis for each thread under `.tmp/email_analysis/THREAD_ID.json`.
- State files under `.tmp/thread_state/THREAD_ID.json` describing the booking lifecycle.
- Proposed time options under `.tmp/time_proposals/THREAD_ID.json`.
- Draft reply emails under `.tmp/email_drafts/THREAD_ID_MESSAGE_ID.json`.
- Calendar events created in the configured Google Calendar.
- (Optional) Log rows appended to the configured Google Sheet when a booking is confirmed.

## Integration with n8n

You can use n8n to automate when this workflow runs and how approvals work.

**Option A – n8n watches Gmail, this project does the heavy lifting**
- In n8n, create a workflow:
  - Trigger: **Gmail** (new message / new thread) using your Google account.
  - Node: **HTTP Request** / **Webhook** to call a local endpoint or automation that, in turn, runs:
    - `gmail_fetch_threads.py` for the relevant `threadId`.
    - `analyze_email_for_booking.py`, `thread_state_manager.py`, `generate_time_proposals.py`, `draft_booking_email_reply.py`.
  - Node: **Respond to Webhook** or **Email** to send you a summary (e.g. “New booking draft ready for THREAD_ID” with a link or the draft content).

**Option B – this project triggers n8n webhooks**
- Register an identity in `workflows/n8n_webhooks.json` (see `[workflows/n8n_setup.md](workflows/n8n_setup.md)`), e.g.:
  ```json
  {
    "email-booking-approve": "https://your-n8n.com/webhook/email-booking-approve"
  }
  ```
- Use `tools/n8n_api.py --trigger-by-name email-booking-approve --data '{\"threadId\":\"...\"}'` when a booking is ready for your review.
- Let the n8n workflow:
  - Fetch the relevant draft from `.tmp/email_drafts/`.
  - Present it in an email or UI for you.
  - Call back into this project (another webhook or manual trigger) to confirm which slot you approved, then run:
    - `create_calendar_event.py`, `send_gmail_message.py`, `thread_state_manager.py`, `log_bookings_to_google_sheet.py`.

You can start simple (manual terminal commands) and gradually move more steps into n8n as you gain confidence.

## Edge cases / notes

- **Ambiguous requests**  
  - If the email doesn’t specify dates/times clearly, `analyze_email_for_booking.py` should set `intent="booking_new"` but mark `requested_time_windows` as low‑confidence.  
  - `draft_booking_email_reply.py` should then:
    - Suggest some reasonable windows based on your working hours.
    - Ask 1–2 clarifying questions instead of over‑committing.

- **Time zones**  
  - All scripts should:
    - Use `BOOKING_TIMEZONE` for formatting times in replies.
    - Make it explicit in email text (e.g. “times below are in HKT (UTC+8)”).

- **Minimum notice & buffers**  
  - `google_calendar_availability.py` should filter out slots earlier than `now + BOOKING_MIN_NOTICE_HOURS`.  
  - Optionally, add fixed buffers before/after existing events when computing free slots.

- **Thread re‑analysis**  
  - Every time a thread receives a new message, re‑run analysis and state updates to handle:
    - Guest picking one of the proposed times.
    - Guest rejecting or modifying previous options.
    - Guest cancelling or asking to reschedule.

- **Failures calling Google or LLM APIs**  
  - Each tool should:
    - Exit with a clear error message on network/auth failures (HTTP 4xx/5xx).  
    - Avoid partially written files (write JSON to a temp file then rename).
  - If a step fails, you can safely re‑run it; `.tmp/` is disposable.

- **Dry runs vs live sending**  
  - During initial testing, only run up to `draft_booking_email_reply.py` and manually inspect drafts.  
  - Once satisfied, enable `create_calendar_event.py` and `send_gmail_message.py` in your workflow.

