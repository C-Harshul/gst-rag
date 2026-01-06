import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "gst-rag-system")

CHROMA_PERSIST_DIR = "data/chroma"
COLLECTION_NAME = "gst-regulations"

# Google Sheets configuration
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "1sP7rb9Fx-U2lYDcpC1Mjy8Z7bBDBwzgTvzGyIWHBzYc")
GOOGLE_SHEETS_SHEET_NAME = os.getenv("GOOGLE_SHEETS_SHEET_NAME", "Queries-Rag")
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "google_sheets_credentials.json")
