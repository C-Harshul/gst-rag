"""FastAPI endpoint for RAG query system."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chain import build_rag_chain
from ingestion.embeddings import CFWorkersAIEmbeddings, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CF_EMBEDDINGS_MODEL
from config.settings import GOOGLE_API_KEY

app = FastAPI(
    title="GST RAG Query API",
    version="1.0.0",
    description="API endpoint for querying the RAG system using LangChain"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    """Request model for RAG query."""
    question: str
    force_refresh: Optional[bool] = False


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    answer: str
    question: str
    status: str = "success"


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GST RAG Query API"
    }


@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest):
    """
    Query the RAG system with a question.
    This endpoint can be called by any frontend to get answers from the LangChain RAG system.
    
    Args:
        request: QueryRequest containing the question
        
    Returns:
        QueryResponse with the answer from the RAG system
    """
    try:
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        # Check if required API keys are configured
        if not GOOGLE_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY is not configured"
            )
        
        # Initialize embedding client
        embedder = CFWorkersAIEmbeddings(
            account_id=CLOUDFLARE_ACCOUNT_ID,
            api_token=CLOUDFLARE_API_TOKEN,
            model=CF_EMBEDDINGS_MODEL
        )
        
        # Build RAG chain
        rag_chain = build_rag_chain(embedder, force_refresh=request.force_refresh)
        
        # Invoke the chain with the question
        answer = rag_chain.invoke(request.question)
        
        return QueryResponse(
            question=request.question,
            answer=answer,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

