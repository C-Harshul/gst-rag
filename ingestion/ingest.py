from ingestion.pdf_loader import load_and_chunk_pdf
from rag.vectorstore import get_vectorstore

def ingest_pdf(pdf_path: str, embedding_client):
    chunks = load_and_chunk_pdf(pdf_path)

    vectordb = get_vectorstore(embedding_client)
    vectordb.add_documents(chunks)
    # Note: persist() is not needed when using HTTP client mode
    # Documents are automatically persisted on the ChromaDB server

    return len(chunks)
