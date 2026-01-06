"""Test script for Google Sheets integration."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag.google_sheets_logger import test_google_sheets_connection, log_to_google_sheets

if __name__ == "__main__":
    print("Testing Google Sheets connection...")
    print("=" * 50)
    
    # Test connection
    success = test_google_sheets_connection()
    
    if success:
        print("\n" + "=" * 50)
        print("Testing log entry...")
        
        # Test logging
        try:
            log_to_google_sheets(
                username="Test User",
                question="This is a test query to verify Google Sheets integration",
                session_id="test-session-123"
            )
            print("✅ Test log entry added successfully!")
            print("\nPlease check your Google Sheet to verify the entry was added.")
        except Exception as e:
            print(f"❌ Error logging test entry: {str(e)}")
    else:
        print("\n❌ Connection test failed. Please check:")
        print("1. The credentials file exists at: google_sheets_credentials.json")
        print("2. The Google Sheet is shared with: harshul@gst-rag.iam.gserviceaccount.com")
        print("3. The service account has 'Editor' permissions")

