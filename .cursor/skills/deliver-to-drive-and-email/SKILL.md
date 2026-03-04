---
name: deliver-to-drive-and-email
description: Delivers files to Google Drive (default folder Shared drives\Sales Department\00_Inbox\11_Inbox_Scott) and/or emails them to the user. Use when the user asks to download a file to Drive, save to Drive, put in Drive, email to myself, email to me, or send me the file.
---

# Deliver to Drive and Email to Me

When the user wants a file **saved to Google Drive** and/or **emailed to themselves**, use the project tools from the **project root** and follow the naming and folder conventions below.

## When to Apply

- User says: "download to Drive", "put in Drive", "save to Drive", "upload to Drive", "email to me", "email to myself", "send me the file", or similar.
- After generating or updating a deliverable (e.g. engagement list, report CSV/Sheet) that should be in Drive and/or in the user's inbox.

## 1. Upload to Google Drive

**Tool:** `tools/google_drive.py`

From project root:

```powershell
py tools/google_drive.py --upload-csv "<path_to_file>" --title "<Name>_<Description>_<YYYYMMDD>"
```

- **Path:** Use the file path (e.g. `.tmp/yesterday_engagement.csv`). CSV is uploaded and converted to a **Google Sheet**.
- **Folder:** Do not pass `--folder-id` unless the user specifies another folder. Default is **Shared drives\Sales Department\00_Inbox\11_Inbox_Scott** (via `GOOGLE_DRIVE_DEFAULT_FOLDER_ID` in `.env`).
- **Title / naming:** Use format **`{Source}_{Description}_{YYYYMMDD}`**. Examples:
  - `Hubspot_EngagementList_Yesterday_20260303`
  - `Report_SalesSummary_20260303`
  Use today’s date for the report date unless the user asks for another date.

After the command runs, the script prints the **Sheet URL** (webViewLink). Capture it for the email step.

## 2. Email to the User

**Tool:** `tools/google_gmail.py`

From project root:

```powershell
py tools/google_gmail.py --send --to <recipient_email> --subject "<Subject>" --body "<Body>" [--attach <path>]
```

- **To (email to me / myself):** Always use **scottwong@mimingmart.com**. For any other recipient, use the address the user specifies.
- **Subject:** Short, descriptive (e.g. "HubSpot: Yesterday engagement list" or "Report: &lt;name&gt;").
- **Body:** Use the 上款／下款 format below. Include the **Drive/Sheet link** when the file was uploaded in step 1.
- **Attachment:** Use `--attach <path>` only if the user asks for the file in email or for a small file; otherwise send the link only.

### Email format (上款／下款)

**上款 (opening):**
```
Dear [Recipient name],
```
- For "email to me" / "myself": use **Dear Scott,** (recipient is Scott Wong).
- For another recipient: use **Dear &lt;their name&gt;,**

**Body content:** One or two lines describing the email (e.g. link to the file, what it contains). Then the closing.

**下款 (closing):**
```
Regards

Scott Wong
Assistant Operation Manager, MI MING MART

Inwell International Limited
16/F, Guangdong Tours Centre, 18 Pennington St, Causeway Bay, Hong Kong
www.mimingmart.com | www.facebook.com/mimingmart
```

**Full body example (email to me, with Drive link):**
```
Dear Scott,

Please find the link to the file: [paste Drive/Sheet URL]

Regards

Scott Wong
Assistant Operation Manager, MI MING MART

Inwell International Limited
16/F, Guangdong Tours Centre, 18 Pennington St, Causeway Bay, Hong Kong
www.mimingmart.com | www.facebook.com/mimingmart
```

## 3. Combined Flow (Drive + Email to Me)

1. Ensure the file exists (generate or export it first if needed).
2. Upload to Drive with the naming format; note the printed Sheet URL.
3. Send an email to the user with:
   - **To:** their address (ask if unknown),
   - **Subject:** descriptive title,
   - **Body:** brief description + **Drive link** (the webViewLink from step 2),
   - **Attach:** the local file only if the user asked for the file in email or for a small file.

## Project Conventions

| Item | Convention |
|------|------------|
| Default Drive folder | Shared drives\Sales Department\00_Inbox\11_Inbox_Scott (set `GOOGLE_DRIVE_DEFAULT_FOLDER_ID` in `.env`) |
| File naming | `{Source}_{Description}_{YYYYMMDD}` (e.g. `Hubspot_EngagementList_Yesterday_20260303`) |
| Run commands from | Project root (e.g. `d:\Agent`) |
| CSV → Sheet | Drive upload converts CSV to Google Sheet automatically |

## Example: Engagement List

User asks: "Put the engagement list in Drive and email it to me."

1. Ensure `.tmp/yesterday_engagement.csv` exists (run HubSpot + export if not).
2. Upload:  
   `py tools/google_drive.py --upload-csv .tmp/yesterday_engagement.csv --title "Hubspot_EngagementList_Yesterday_20260303"`
3. Copy the printed Sheet URL.
4. Email:  
   `py tools/google_gmail.py --send --to scottwong@mimingmart.com --subject "HubSpot: Yesterday engagement list" --body "Link to the list: <paste Sheet URL>" --attach .tmp/yesterday_engagement.csv`  
   (Omit `--attach` if you prefer link-only.)
