from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid
import sys
import os

# Add parent dir to path so we can import rag_engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from nlp.rag_engine import rag_engine
except ImportError:
    rag_engine = None

router = APIRouter(prefix="/api/chat", tags=["NLP Chatbot"])

# In-memory session store
sessions: Dict[str, List[Dict[str, str]]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if rag_engine is None:
        raise HTTPException(status_code=500, detail="NLP Engine not available. Check server logs.")

    session_id = req.session_id
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    # Keep only the last 5 exchanges to avoid context window explosion
    history = sessions[session_id][-10:]
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    # Construct memory-augmented query
    memory_augmented_query = f"Previous messages:\n{history_str}\n\nNew query: {req.message}" if history else req.message

    try:
        # Save user message
        sessions[session_id].append({"role": "user", "content": req.message})
        
        # We don't augment the full history into the RagEngine system prompt since it handles its own formatting,
        # but we could just pass history strings into the User Question area.
        # RAG Engine will extract the VEHICLE_ID if present in the new message
        response_text = await rag_engine.retrieve_and_generate(memory_augmented_query)
        
        # Save AI message
        sessions[session_id].append({"role": "assistant", "content": response_text})

        return ChatResponse(response=response_text, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{session_id}", response_model=List[Dict[str, str]])
async def get_chat_history(session_id: str):
    if session_id in sessions:
        return sessions[session_id]
    raise HTTPException(status_code=404, detail="Session not found")
