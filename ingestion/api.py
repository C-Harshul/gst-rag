"""FastAPI endpoint for vectorizing PDFs from S3."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
import sys
import traceback

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed messages."""
    errors = exc.errors()
    error_details = []
    for error in errors:
        error_details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    print(f"❌ Validation error on {request.url.path}: {error_details}")
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Request validation failed",
            "errors": error_details,
            "body_received": str(exc.body) if hasattr(exc, 'body') else None
        }
    )


class S3IngestRequest(BaseModel):
    """Request model for S3 PDF ingestion."""
    bucket: str = Field(..., description="S3 bucket name", min_length=1)
    key: str = Field(..., description="S3 object key (file path)", min_length=1)
    chunk_size: Optional[int] = Field(default=1000, ge=100, le=10000, description="Size of text chunks")
    chunk_overlap: Optional[int] = Field(default=200, ge=0, le=1000, description="Overlap between chunks")
    collection_name: Optional[str] = Field(default=None, description="Name of the collection to add the document to. Defaults to 'gst-regulations' if not provided")


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
        request: S3IngestRequest containing bucket, key, and optional collection_name
        
    Returns:
        S3IngestResponse with processing results
    """
    try:
        # Validate that it's a PDF
        if not request.key.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail=f"File {request.key} is not a PDF file. Only .pdf files are supported."
            )
        
        # Validate bucket and key are not empty
        if not request.bucket or not request.bucket.strip():
            raise HTTPException(
                status_code=400,
                detail="Bucket name cannot be empty"
            )
        if not request.key or not request.key.strip():
            raise HTTPException(
                status_code=400,
                detail="S3 key cannot be empty"
            )
        
        # Determine collection name (default to "gst-regulations" if not provided)
        collection_name = request.collection_name or "gst-regulations"
        
        print(f"Processing S3 PDF: s3://{request.bucket}/{request.key}")
        print(f"Using collection: {collection_name}")
        
        # Initialize components
        print("Initializing PDFLoader...")
        pdf_loader = PDFLoader(
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        print("Initializing embeddings...")
        embeddings = GSTEmbeddings(cf_embedder)
        print(f"Connecting to vectorstore with collection: {collection_name}...")
        vectorstore = get_vectorstore(cf_embedder, collection_name=collection_name)
        print("Vectorstore connection established.")
        
        # Load and chunk PDF from S3
        print("Loading and chunking PDF from S3...")
        try:
            documents = pdf_loader.load_from_s3(request.bucket, request.key)
            print(f"Created {len(documents)} chunks")
        except ValueError as e:
            # Handle unsupported PDF format errors
            raise HTTPException(
                status_code=400,
                detail=f"Cannot extract text from PDF at s3://{request.bucket}/{request.key}. {str(e)}"
            )
        except FileNotFoundError as e:
            # Handle S3 object not found
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )
        except PermissionError as e:
            # Handle permission errors
            raise HTTPException(
                status_code=403,
                detail=str(e)
            )
        
        if not documents:
            raise HTTPException(
                status_code=400,
                detail=f"No content extracted from PDF at s3://{request.bucket}/{request.key}. The file may be empty, corrupted, password-protected, or in an unsupported format."
            )
        
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
        error_trace = traceback.format_exc()
        print(f"❌ Error processing s3://{request.bucket}/{request.key}: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

