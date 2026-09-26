import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()  # before importing agent: it reads the environment at import time

# AGENT_IMPL=loop (default): our for-loop in agent.py; AGENT_IMPL=graph: LangGraph in agent_graph.py
if os.getenv("AGENT_IMPL", "loop") == "graph":
    from agent_graph import chat  # noqa: E402
else:
    from agent import chat  # noqa: E402

app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    history: list = []


@app.post("/api/chat")
def chat_route(request: ChatRequest):
    # Always answer with JSON, so the UI can show the error instead of hanging
    try:
        return {"answer": chat(request.message, request.history)}
    except Exception as e:
        return {"answer": f"Error: {type(e).__name__}: {e}"}
