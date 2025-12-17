"""Script to ingest GST regulation PDFs into the vector store."""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ingestion.pdf_loader import PDFLoader
from ingestion.embeddings import cf_embedder, GSTEmbeddings
from rag.vectorstore import get_vectorstore, add_documents_safely


def ingest_pdf(pdf_path: str):
    """
    Ingest a single PDF file into the vector store.
    
    Args:
        pdf_path: Path to the PDF file
    """
    print(f"Processing PDF: {pdf_path}")
    
    # Initialize components
    pdf_loader = PDFLoader()
    embeddings = GSTEmbeddings(cf_embedder)
    vectorstore = get_vectorstore(cf_embedder)
    
    try:
        # Load and chunk PDF
        print("Loading and chunking PDF...")
        documents = pdf_loader.load_from_file(pdf_path)
        print(f"Created {len(documents)} chunks")
        
        # Add to vector store safely (embeddings will be generated automatically)
        print("Adding to vector store...")
        total_added = add_documents_safely(vectorstore, documents)
        
        print(f"✅ Successfully ingested {total_added} chunks from {pdf_path}")
        
    except Exception as e:
        print(f"❌ Error processing {pdf_path}: {str(e)}")


def ingest_directory(directory_path: str):
    """
    Ingest all PDF files from a directory.
    
    Args:
        directory_path: Path to directory containing PDFs
    """
    directory = Path(directory_path)
    pdf_files = list(directory.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {directory_path}")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_file in pdf_files:
        ingest_pdf(str(pdf_file))
        print("-" * 50)


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ingest_documents.py <pdf_file_or_directory>")
        print("\nExamples:")
        print("  python ingest_documents.py documents/gst_rules.pdf")
        print("  python ingest_documents.py documents/")
        return
        
    path = sys.argv[1]
    
    if not os.path.exists(path):
        print(f"Error: Path '{path}' does not exist")
        return
        
    if os.path.isfile(path) and path.lower().endswith('.pdf'):
        ingest_pdf(path)
    elif os.path.isdir(path):
        ingest_directory(path)
    else:
        print(f"Error: '{path}' is not a PDF file or directory")


if __name__ == "__main__":
    main()