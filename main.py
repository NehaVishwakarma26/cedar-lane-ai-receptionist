import uvicorn
import logging

import agent
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    reply: str

@app.get("/health")
def health_check():
    return {"message":"Working!"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Forward a chat turn to the UI-agnostic receptionist agent."""
    try:
        reply = agent.respond(request.session_id, request.message)
        return ChatResponse(session_id=request.session_id, reply=reply)
    except Exception as exc:
        log.exception("Chat request failed")
        raise HTTPException(
            status_code=502,
            detail="The receptionist could not complete that request. Please try again.",
        ) from exc

def main():
    print("Hello from procindex-assignment!")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
