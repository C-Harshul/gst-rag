# Quick Setup Instructions - Google Sheets Integration

## ✅ What's Done:
- ✅ Credentials file renamed and configured
- ✅ Packages installed
- ✅ Connection test successful
- ✅ Spreadsheet and sheet found

## ⚠️ One Step Remaining:

### Share the Google Sheet with Service Account

**The service account needs permission to write to your sheet.**

1. **Open your Google Sheet:**
   https://docs.google.com/spreadsheets/d/1sP7rb9Fx-U2lYDcpC1Mjy8Z7bBDBwzgTvzGyIWHBzYc/edit

2. **Click "Share" button** (top right corner)

3. **Add this email address:**
   ```
   harshul@gst-rag.iam.gserviceaccount.com
   ```

4. **Set permission to "Editor"** (not Viewer)

5. **Click "Share"**

6. **Verify it works:**
   ```bash
   python test_google_sheets.py
   ```

## After Sharing:

Once you share the sheet, the system will automatically log:
- **Timestamp** - When the query was made
- **Name** - Username from the request
- **Query** - The question asked
- **Session ID** - Session identifier

All queries (with or without username) will be logged to the "Queries-Rag" sheet.

## Current Status:

- ✅ Credentials: Configured
- ✅ Connection: Working
- ⏳ Permissions: **Waiting for you to share the sheet**

