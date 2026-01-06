# Google Sheets Integration Setup

This guide explains how to set up Google Sheets integration to log username and query data.

## Overview

The system automatically logs each query with username to a Google Sheet for tracking and analytics. The data is written to the "Queries-Rag" sheet in the specified spreadsheet.

## Setup Steps

### 1. Create a Google Cloud Project and Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

4. Create a Service Account:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in the service account details
   - Click "Create and Continue"
   - Skip the optional steps and click "Done"

5. Create a Key for the Service Account:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Download the JSON file

### 2. Share the Google Sheet with Service Account

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1sP7rb9Fx-U2lYDcpC1Mjy8Z7bBDBwzgTvzGyIWHBzYc/edit
2. Click the "Share" button
3. Get the service account email from the downloaded JSON file (it looks like: `your-service-account@project-id.iam.gserviceaccount.com`)
4. Share the sheet with this email address with "Editor" permissions
5. Make sure the sheet "Queries-Rag" exists (it will be created automatically if it doesn't)

### 3. Configure Credentials

1. Rename the downloaded JSON file to `google_sheets_credentials.json`
2. Place it in the project root directory (same level as `requirements.txt`)
3. Alternatively, set the path in your `.env` file:
   ```
   GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/google_sheets_credentials.json
   ```

### 4. Environment Variables (Optional)

You can customize the configuration via environment variables:

```bash
# .env file
GOOGLE_SHEETS_SPREADSHEET_ID=1sP7rb9Fx-U2lYDcpC1Mjy8Z7bBDBwzgTvzGyIWHBzYc
GOOGLE_SHEETS_SHEET_NAME=Queries-Rag
GOOGLE_SHEETS_CREDENTIALS_PATH=google_sheets_credentials.json
```

## How It Works

1. When a query is received with a username, the system logs it to Google Sheets
2. Each row contains:
   - **Timestamp**: When the query was made
   - **Name**: Username from the request
   - **Query**: The question asked
   - **Session ID**: Session identifier for tracking conversations

3. The sheet is automatically created if it doesn't exist
4. If Google Sheets logging fails, the query still processes normally (non-blocking)

## Testing

To test the connection, you can run:

```python
from rag.google_sheets_logger import test_google_sheets_connection
test_google_sheets_connection()
```

## Troubleshooting

### "Credentials file not found"
- Make sure `google_sheets_credentials.json` is in the project root
- Or set `GOOGLE_SHEETS_CREDENTIALS_PATH` in `.env`

### "Permission denied" or "Access denied"
- Make sure you've shared the Google Sheet with the service account email
- The service account needs "Editor" permissions

### "Worksheet not found"
- The sheet "Queries-Rag" will be created automatically
- Or create it manually in the spreadsheet

### Logging fails silently
- Check server logs for error messages
- The system continues to work even if Google Sheets logging fails
- Check that the Google Sheets API is enabled in your Google Cloud project

## Security Notes

- **Never commit** `google_sheets_credentials.json` to version control
- Add it to `.gitignore`:
  ```
  google_sheets_credentials.json
  ```
- Keep the credentials file secure and limit access

