# Share Google Sheet with Service Account

## Quick Setup

**Service Account Email:** `harshul@gst-rag.iam.gserviceaccount.com`

### Steps:

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1sP7rb9Fx-U2lYDcpC1Mjy8Z7bBDBwzgTvzGyIWHBzYc/edit

2. Click the **"Share"** button (top right)

3. In the "Add people and groups" field, paste this email:
   ```
   harshul@gst-rag.iam.gserviceaccount.com
   ```

4. Set permission to **"Editor"**

5. Uncheck "Notify people" (optional - service accounts don't need notifications)

6. Click **"Share"**

7. The service account now has access to write to your sheet!

### Verify:

After sharing, run the test script:
```bash
python test_google_sheets.py
```

This will test the connection and add a test entry to verify everything works.

