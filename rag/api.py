"""FastAPI endpoint for RAG query system."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Tuple
import os
import sys
import uuid
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chain import build_rag_chain
from ingestion.embeddings import CFWorkersAIEmbeddings, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CF_EMBEDDINGS_MODEL
from config.settings import GOOGLE_API_KEY

# In-memory session storage (in production, use Redis or a database)
# Format: {session_id: [(question, answer, timestamp), ...]}
session_memory: Dict[str, List[Tuple[str, str, datetime]]] = {}

# Session expiration time (24 hours)
SESSION_EXPIRY = timedelta(hours=24)

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
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation memory. If not provided, a new session will be created.")
    collection_name: Optional[str] = Field(default=None, description="Name of the collection to query from. Defaults to 'gst-regulations' if not provided")
    force_refresh: Optional[bool] = False


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    answer: str
    question: str
    session_id: str = Field(description="Session ID for this conversation")
    status: str = "success"
    sources: Optional[Dict[str, int]] = Field(
        default=None, 
        description="Number of documents retrieved from each collection"
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GST RAG Query API"
    }


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    """Clear conversation history for a session."""
    if session_id in session_memory:
        del session_memory[session_id]
        return {"status": "success", "message": f"Session {session_id} cleared"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


def get_or_create_session(session_id: Optional[str]) -> str:
    """Get existing session or create a new one."""
    if session_id and session_id in session_memory:
        # Check if session has expired
        if session_memory[session_id]:
            last_timestamp = session_memory[session_id][-1][2]
            if datetime.now() - last_timestamp < SESSION_EXPIRY:
                return session_id
            else:
                # Session expired, remove it
                del session_memory[session_id]
    
    # Create new session
    new_session_id = str(uuid.uuid4())
    session_memory[new_session_id] = []
    return new_session_id


def get_conversation_history(session_id: str, max_turns: int = 10) -> List[Tuple[str, str]]:
    """Get conversation history for a session (last N turns)."""
    if session_id not in session_memory:
        return []
    
    history = session_memory[session_id]
    # Return last max_turns conversations (question, answer pairs)
    recent_history = history[-max_turns:] if len(history) > max_turns else history
    return [(q, a) for q, a, _ in recent_history]


def save_conversation(session_id: str, question: str, answer: str):
    """Save conversation to session memory."""
    if session_id not in session_memory:
        session_memory[session_id] = []
    
    session_memory[session_id].append((question, answer, datetime.now()))


@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest):
    """
    Query the RAG system with a question.
    This endpoint supports conversational memory through session IDs.
    
    Args:
        request: QueryRequest containing the question, optional session_id, and optional collection_name
        
    Returns:
        QueryResponse with the answer from the RAG system and session_id
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
        
        # Get or create session
        session_id = get_or_create_session(request.session_id)
        
        # Get conversation history for this session
        conversation_history = get_conversation_history(session_id)
        
        # Determine collection name (default to "gst-regulations" if not provided)
        collection_name = request.collection_name or "gst-regulations"
        
        # Initialize embedding client
        embedder = CFWorkersAIEmbeddings(
            account_id=CLOUDFLARE_ACCOUNT_ID,
            api_token=CLOUDFLARE_API_TOKEN,
            model=CF_EMBEDDINGS_MODEL
        )
        
        # Build RAG chain with specified collection and conversation history
        rag_chain = build_rag_chain(
            embedder, 
            collection_name=collection_name, 
            force_refresh=request.force_refresh,
            conversation_history=conversation_history
        )
        
        # Reset source tracker before invocation
        source_tracker = getattr(rag_chain, '_source_tracker', None)
        if source_tracker:
            source_tracker.sources = {"EY-Papers": 0, "Cases": 0}
        
        # Invoke the chain with the question
        answer = rag_chain.invoke(request.question)
        
        # Save conversation to memory
        save_conversation(session_id, request.question, answer)
        
        # Get source counts from the chain (if available)
        sources = source_tracker.get() if source_tracker else None
        
        return QueryResponse(
            question=request.question,
            answer=answer,
            session_id=session_id,
            status="success",
            sources=sources
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

