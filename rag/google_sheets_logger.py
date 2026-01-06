"""Google Sheets integration for logging queries."""

import os
from typing import Optional
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

from config.settings import (
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_SHEET_NAME,
    GOOGLE_SHEETS_CREDENTIALS_PATH
)

# Cache for the Google Sheets client
_gs_client: Optional[gspread.Client] = None


def get_google_sheets_client() -> Optional[gspread.Client]:
    """
    Get or create Google Sheets client using service account credentials.
    
    Returns:
        gspread.Client if credentials are available, None otherwise
    """
    global _gs_client
    
    if _gs_client is not None:
        return _gs_client
    
    # Check if credentials file exists
    credentials_path = GOOGLE_SHEETS_CREDENTIALS_PATH
    
    # Try absolute path first, then relative to project root
    if not os.path.exists(credentials_path):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        credentials_path = os.path.join(project_root, credentials_path)
    
    if not os.path.exists(credentials_path):
        print(f"[GOOGLE SHEETS] Credentials file not found at: {credentials_path}")
        print(f"[GOOGLE SHEETS] Google Sheets logging will be disabled.")
        print(f"[GOOGLE SHEETS] To enable, create a service account and download credentials JSON file.")
        return None
    
    try:
        # Define the scope
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials
        creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
        
        # Create client
        _gs_client = gspread.authorize(creds)
        print(f"[GOOGLE SHEETS] Successfully connected to Google Sheets")
        return _gs_client
    
    except Exception as e:
        print(f"[GOOGLE SHEETS] Error connecting to Google Sheets: {str(e)}")
        print(f"[GOOGLE SHEETS] Google Sheets logging will be disabled.")
        return None


def log_to_google_sheets(username: str, question: str, session_id: Optional[str] = None):
    """
    Log username and query to Google Sheets.
    
    Args:
        username: Username of the person asking the question
        question: The question being asked
        session_id: Optional session ID
    """
    try:
        client = get_google_sheets_client()
        if client is None:
            return  # Silently fail if credentials not available
        
        # Open the spreadsheet
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
        
        # Get the worksheet (sheet)
        try:
            worksheet = spreadsheet.worksheet(GOOGLE_SHEETS_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            # If sheet doesn't exist, create it
            worksheet = spreadsheet.add_worksheet(
                title=GOOGLE_SHEETS_SHEET_NAME,
                rows=1000,
                cols=10
            )
            # Add headers if it's a new sheet
            worksheet.append_row(["Timestamp", "Name", "Query", "Session ID"])
        
        # Prepare the row data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            timestamp,
            username,
            question,
            session_id or ""
        ]
        
        # Append the row
        worksheet.append_row(row_data)
        print(f"[GOOGLE SHEETS] Successfully logged query to sheet '{GOOGLE_SHEETS_SHEET_NAME}'")
        
    except Exception as e:
        # Don't fail the request if Google Sheets logging fails
        print(f"[GOOGLE SHEETS] Error logging to Google Sheets: {str(e)}")
        print(f"[GOOGLE SHEETS] Query will still be processed, but not logged to sheet.")


def test_google_sheets_connection():
    """
    Test function to verify Google Sheets connection.
    """
    client = get_google_sheets_client()
    if client:
        try:
            spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(GOOGLE_SHEETS_SHEET_NAME)
            print(f"[GOOGLE SHEETS] Connection test successful!")
            print(f"[GOOGLE SHEETS] Spreadsheet: {spreadsheet.title}")
            print(f"[GOOGLE SHEETS] Sheet: {worksheet.title}")
            return True
        except Exception as e:
            print(f"[GOOGLE SHEETS] Connection test failed: {str(e)}")
            return False
    return False

