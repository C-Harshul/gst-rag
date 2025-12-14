import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "gst-rag-system")

CHROMA_PERSIST_DIR = "data/chroma"
COLLECTION_NAME = "gst-regulations"
