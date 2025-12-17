"""FastAPI endpoint for vectorizing PDFs from S3."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pdf_loader import PDFLoader
from ingestion.embeddings import cf_embedder, GSTEmbeddings
from rag.vectorstore import get_vectorstore, add_documents_safely

app = FastAPI(
    title="GST RAG Ingestion API",
    version="1.0.0",
    description="API endpoint for vectorizing PDFs from S3"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class S3IngestRequest(BaseModel):
    """Request model for S3 PDF ingestion."""
    bucket: str
    key: str
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 200


class S3IngestResponse(BaseModel):
    """Response model for S3 PDF ingestion."""
    status: str
    chunks_processed: int
    s3_location: str
    message: str
    metadata: Optional[dict] = None


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "GST RAG Ingestion API"}


@app.post("/ingest/s3", response_model=S3IngestResponse)
def ingest_s3_pdf(request: S3IngestRequest):
    """
    Vectorize a PDF from S3.
    
    This endpoint can be called by a Lambda function to process PDFs uploaded to S3.
    
    Args:
        request: S3IngestRequest containing bucket and key
        
    Returns:
        S3IngestResponse with processing results
    """
    try:
        # Validate that it's a PDF
        if not request.key.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail=f"File {request.key} is not a PDF file"
            )
        
        print(f"Processing S3 PDF: s3://{request.bucket}/{request.key}")
        
        # Initialize components
        pdf_loader = PDFLoader(
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        embeddings = GSTEmbeddings(cf_embedder)
        vectorstore = get_vectorstore(cf_embedder)
        
        # Load and chunk PDF from S3
        print("Loading and chunking PDF from S3...")
        documents = pdf_loader.load_from_s3(request.bucket, request.key)
        print(f"Created {len(documents)} chunks")
        
        # Add to vector store safely
        print("Adding to vector store...")
        total_added = add_documents_safely(vectorstore, documents)
        
        # Extract metadata
        metadata = pdf_loader.extract_metadata(documents)
        
        print(f"✅ Successfully ingested {total_added} chunks from s3://{request.bucket}/{request.key}")
        
        return S3IngestResponse(
            status="success",
            chunks_processed=total_added,
            s3_location=f"s3://{request.bucket}/{request.key}",
            message=f"Successfully processed {total_added} chunks",
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing s3://{request.bucket}/{request.key}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

