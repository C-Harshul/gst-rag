"""FastAPI endpoint for RAG query system."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Tuple
import os
import sys
import uuid
from datetime import datetime, timedelta
import asyncio
from functools import wraps

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chain import build_rag_chain
from rag.clarification import detect_clarification, combine_question_with_clarification
from rag.google_sheets_logger import log_to_google_sheets
from ingestion.embeddings import CFWorkersAIEmbeddings, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CF_EMBEDDINGS_MODEL
from config.settings import GOOGLE_API_KEY

# In-memory session storage (in production, use Redis or a database)
# Format: {session_id: [(question, answer, timestamp), ...]}
session_memory: Dict[str, List[Tuple[str, str, datetime]]] = {}

# Pending clarifications storage
# Format: {session_id: {"original_question": str, "clarification_question": str, "context": str, "timestamp": datetime}}
pending_clarifications: Dict[str, Dict] = {}

# Session expiration time (24 hours)
SESSION_EXPIRY = timedelta(hours=24)

# Clarification expiration time (5 minutes)
CLARIFICATION_EXPIRY = timedelta(minutes=5)

app = FastAPI(
    title="GST RAG Query API",
    version="1.0.0",
    description="API endpoint for querying the RAG system using LangChain"
)

# Configure timeout settings
# For AWS deployments, increase these values based on your infrastructure:
# - API Gateway: Max 30 seconds (use Lambda integration for longer)
# - Lambda: Up to 15 minutes (configure in Lambda settings)
# - ALB: Default 60 seconds (can be increased to 4000 seconds)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))  # 5 minutes default

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
    username: Optional[str] = Field(default=None, description="Username of the person asking the question. Used for tracking in LangSmith.")
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
    requires_clarification: bool = Field(
        default=False,
        description="Whether the response requires clarification from the user"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="The clarification question asked to the user"
    )
    pending_question: Optional[str] = Field(
        default=None,
        description="The original question that is pending clarification"
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
    """Clear conversation history and pending clarifications for a session."""
    session_found = False
    
    if session_id in session_memory:
        del session_memory[session_id]
        session_found = True
    
    if session_id in pending_clarifications:
        del pending_clarifications[session_id]
        session_found = True
    
    if session_found:
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


def save_pending_clarification(session_id: str, original_question: str, clarification_question: str, context: str = ""):
    """Save a pending clarification for a session."""
    pending_clarifications[session_id] = {
        "original_question": original_question,
        "clarification_question": clarification_question,
        "context": context,
        "timestamp": datetime.now()
    }


def get_pending_clarification(session_id: str) -> Optional[Dict]:
    """Get pending clarification for a session if it exists and hasn't expired."""
    if session_id not in pending_clarifications:
        return None
    
    clarification = pending_clarifications[session_id]
    
    # Check if clarification has expired
    if datetime.now() - clarification["timestamp"] > CLARIFICATION_EXPIRY:
        # Clear expired clarification
        del pending_clarifications[session_id]
        return None
    
    return clarification


def clear_pending_clarification(session_id: str):
    """Clear pending clarification for a session."""
    if session_id in pending_clarifications:
        del pending_clarifications[session_id]


def clear_expired_clarifications():
    """Clear all expired clarifications across all sessions."""
    expired_sessions = []
    for session_id, clarification in pending_clarifications.items():
        if datetime.now() - clarification["timestamp"] > CLARIFICATION_EXPIRY:
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del pending_clarifications[session_id]


def log_user_query(username: str, question: str, session_id: str):
    """
    Log query with username for analytics/tracking purposes.
    This is for backend tracking only and does NOT affect the LLM response.
    
    Args:
        username: Username of the person asking the question (from request body)
        question: The question being asked
        session_id: Session ID for the conversation
    """
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "username": username,
        "question": question[:100] + "..." if len(question) > 100 else question,  # Truncate for logging
        "session_id": session_id
    }
    
    # Log to console with username prominently displayed and source information
    print(f"[QUERY LOG] ========================================")
    print(f"[QUERY LOG] Username Source: Request Body (username field)")
    print(f"[QUERY LOG] Username Value: '{username}'")
    print(f"[QUERY LOG] Session ID: {session_id}")
    print(f"[QUERY LOG] Question: {question[:100]}{'...' if len(question) > 100 else ''}")
    print(f"[QUERY LOG] Timestamp: {timestamp}")
    print(f"[QUERY LOG] ========================================")
    
    # TODO: In production, you might want to:
    # - Store in database: database.logs.insert(log_entry)
    # - Send to analytics service: analytics.track("query", log_entry)
    # - Write to log file: logger.info(json.dumps(log_entry))


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the RAG system with a question.
    This endpoint supports conversational memory through session IDs and clarification feedback loops.
    
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
        
        # Clear expired clarifications
        clear_expired_clarifications()
        
        # Get or create session first (needed for logging)
        session_id = get_or_create_session(request.session_id)
        
        # Track query with username (for analytics only - NOT used in LLM prompts)
        if request.username:
            print(f"[QUERY LOG] Username received from request: '{request.username}'")
            log_user_query(
                username=request.username,
                question=request.question,
                session_id=session_id
            )
            # Log to Google Sheets
            try:
                log_to_google_sheets(
                    username=request.username,
                    question=request.question,
                    session_id=session_id
                )
            except Exception as e:
                print(f"[QUERY LOG] Failed to log to Google Sheets: {str(e)}")
        else:
            # Log even if no username provided (for tracking anonymous queries)
            print(f"[QUERY LOG] No username provided in request - logging as Anonymous")
            print(f"[QUERY LOG] User: Anonymous | Session: {session_id} | Question: {request.question[:100]}...")
            print(f"[QUERY LOG] Timestamp: {datetime.now().isoformat()}")
            # Log anonymous queries to Google Sheets too
            try:
                log_to_google_sheets(
                    username="Anonymous",
                    question=request.question,
                    session_id=session_id
                )
            except Exception as e:
                print(f"[QUERY LOG] Failed to log to Google Sheets: {str(e)}")
        
        # Check if there's a pending clarification for this session
        pending_clarification = get_pending_clarification(session_id)
        
        # Determine the actual question to process
        actual_question = request.question
        is_clarification_response = False
        original_question_for_clarification = None
        
        if pending_clarification:
            # This is a response to a clarification question
            is_clarification_response = True
            original_question_for_clarification = pending_clarification["original_question"]
            clarification_response = request.question
            
            # Combine original question with clarification response
            actual_question = combine_question_with_clarification(
                original_question_for_clarification,
                clarification_response
            )
            
            # Clear the pending clarification since we're processing it
            clear_pending_clarification(session_id)
        
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
        
        # Prepare LangSmith config with username and session_id for tracking
        langsmith_config = {}
        
        # Add username to tags and metadata if provided
        if request.username:
            langsmith_config["tags"] = [f"user:{request.username}"]
            langsmith_config["metadata"] = {
                "username": request.username,
                "session_id": session_id
            }
        else:
            langsmith_config["metadata"] = {
                "session_id": session_id
            }
        
        # Create a wrapper function to invoke with config
        def invoke_with_config():
            return rag_chain.invoke(actual_question, config=langsmith_config)
        
        # Invoke the chain with the question (use actual_question which may be enhanced)
        # Run in executor to avoid blocking and allow timeout handling
        loop = asyncio.get_event_loop()
        answer = await asyncio.wait_for(
            loop.run_in_executor(None, invoke_with_config),
            timeout=REQUEST_TIMEOUT
        )
        
        # Check if the response contains a clarification question
        clarification_info = detect_clarification(answer)
        
        # Save conversation to memory (use the original question, not the enhanced one)
        save_conversation(session_id, request.question, answer)
        
        # Get source counts from the chain (if available)
        sources = source_tracker.get() if source_tracker else None
        
        # If clarification is detected, save it and return clarification status
        if clarification_info and clarification_info.get("detected"):
            # Use the original question (before clarification) if this was a clarification response
            question_to_save = original_question_for_clarification if is_clarification_response else request.question
            
            save_pending_clarification(
                session_id=session_id,
                original_question=question_to_save,
                clarification_question=clarification_info["clarification_question"],
                context=clarification_info.get("original_context", "")
            )
            
            return QueryResponse(
                question=request.question,
                answer=answer,
                session_id=session_id,
                status="success",
                sources=sources,
                requires_clarification=True,
                clarification_question=clarification_info["clarification_question"],
                pending_question=question_to_save
            )
        
        # Normal response without clarification needed
        return QueryResponse(
            question=request.question,
            answer=answer,
            session_id=session_id,
            status="success",
            sources=sources,
            requires_clarification=False,
            clarification_question=None,
            pending_question=None
        )
        
    except asyncio.TimeoutError:
        print(f"❌ Query timeout after {REQUEST_TIMEOUT} seconds")
        raise HTTPException(
            status_code=504,
            detail=f"Request timeout. The query took longer than {REQUEST_TIMEOUT} seconds to process. Please try a simpler query or contact support."
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing query: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    # Increase timeout for uvicorn server
    # timeout_keep_alive: Time to keep connections alive
    # timeout_graceful_shutdown: Time to wait for graceful shutdown
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8002,
        timeout_keep_alive=300,  # 5 minutes
        timeout_graceful_shutdown=30
    )

