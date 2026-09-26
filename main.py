import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()  # before importing the agents: they read the environment at import time

from agent import chat as loop_chat  # noqa: E402
from agent_graph import chat as graph_chat  # noqa: E402

# loop: our for-loop in agent.py; graph: LangGraph in agent_graph.py
CHATS = {"loop": loop_chat, "graph": graph_chat}
DEFAULT_IMPL = os.getenv("AGENT_IMPL", "loop")

app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    history: list = []
    impl: Literal["loop", "graph"] | None = None  # the UI's toggle; AGENT_IMPL if omitted


@app.post("/api/chat")
def chat_route(request: ChatRequest):
    impl = request.impl or DEFAULT_IMPL
    # Always answer with JSON, so the UI can show the error instead of hanging
    try:
        answer = CHATS[impl](request.message, request.history)
    except Exception as e:
        answer = f"Error: {type(e).__name__}: {e}"
    return {"answer": answer, "impl": impl}
