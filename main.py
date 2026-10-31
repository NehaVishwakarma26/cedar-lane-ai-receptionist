import uvicorn
import logging

import agent
from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

app = FastAPI()
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    saved_to_sheets: bool


class SessionEndResponse(BaseModel):
    session_id: str
    logged: bool

@app.get("/health")
def health_check():
    return {"message":"Working!"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Forward a chat turn to the UI-agnostic receptionist agent."""
    try:
        reply = agent.respond(request.session_id, request.message)
        saved = agent.save_session(request.session_id)
        return ChatResponse(session_id=request.session_id, reply=reply, saved_to_sheets=saved)
    except Exception as exc:
        log.exception("Chat request failed")
        try:
            agent.save_session(request.session_id)
        except Exception:
            log.exception("Could not save failed chat session %s", request.session_id)
        raise HTTPException(
            status_code=502,
            detail="The receptionist could not complete that request. Please try again.",
        ) from exc


@app.post("/sessions/{session_id}/end", response_model=SessionEndResponse)
def end_chat_session(session_id: str = Path(min_length=1, max_length=200)):
    """Finalize a chat when the user starts another conversation."""
    try:
        logged = agent.end_session(session_id)
    except Exception as exc:
        log.exception("Failed to finalize chat session %s", session_id)
        raise HTTPException(status_code=502, detail="Could not save this conversation to Google Sheets.") from exc
    if not logged:
        raise HTTPException(
            status_code=502,
            detail="Could not save this conversation to Google Sheets. Please retry.",
        )
    return SessionEndResponse(session_id=session_id, logged=True)

def main():
    print("Hello from procindex-assignment!")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
