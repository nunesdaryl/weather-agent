# Weather Agent

FDE course exercise. An AI agent is a language model, a few tools it can call,
and a loop that runs them until it has an answer.

Repo: https://github.com/nunesdaryl/weather-agent

```
React UI  ->  FastAPI      ->  Agent loop      ->  Tool
App.jsx       POST /api/chat   chat(), max 5       get_weather -> Open-Meteo
```

## Files

| file | what it is |
|---|---|
| `.env` | Azure AI Foundry endpoint, key, deployment name. **Never commit.** |
| `agent.py` | The tool (`get_weather`), the model, and the agent loop (`chat`). |
| `main.py` | FastAPI server with one route, `POST /api/chat`, that calls either agent's `chat()`. |
| `frontend/src/App.jsx` | React chat box with a LangChain / LangGraph / side-by-side toggle. |
| `requirements.txt` | langchain-azure-ai, langchain, fastapi, uvicorn, httpx, python-dotenv, pytest |
| `agent_graph.py` | The same agent on LangGraph (`create_agent`). Picked with the toggle in the UI. |
| `test_agent.py`, `test_agent_graph.py` | Tests for the tool and both loops. Not part of the exercise. |

## Run it

```bash
# 0. get the code
git clone https://github.com/nunesdaryl/weather-agent.git && cd weather-agent

# 1. fill in .env from the Foundry portal
cp .env.example .env

# 2. backend on :8000
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8000

# 3. UI on http://localhost:5173
cd frontend && npm install && npm run dev
```

## The loop

```python
for _ in range(5):                  # 1. cap: 5 calls
    reply = model.invoke(messages)  # 2. think
    messages.append(reply)
    if not reply.tool_calls:        # 3. stop  - the text is the answer
        return reply.text
    for call in reply.tool_calls:   # 4. act   - run the tool, append a ToolMessage
        ...
                                    # 5. repeat - back to think
```

- **Messages** — system prompt, then history, then the new question.
- **Think** — the model replies with text or a tool call.
- **Stop** — no tool calls means the text is the answer.
- **Act** — run the tool, append the result as a `ToolMessage` tagged with the
  id the model used to ask.
- **Repeat** — back to Think. The cap stops endless loops.

The model decides whether to call `get_weather` by reading its **docstring**.
Write that docstring for the model.

The tool never raises: a missing city or a network error comes back as a string,
so the model can recover instead of the loop crashing. Weather codes are turned
into words ("cloudy") by the tool, so the model doesn't have to guess.

## The same agent on LangGraph

`agent_graph.py` is the same agent with LangGraph running the loop. It uses
the same tool and system prompt; only the loop is different.

| agent.py (by hand) | agent_graph.py (LangGraph) |
|---|---|
| `model.bind_tools([get_weather])` | `create_agent(model, tools=[get_weather])` binds them |
| `for _ in range(5)` | `ModelCallLimitMiddleware(run_limit=5)` |
| `if not reply.tool_calls: return` | the graph ends when the model stops calling tools |
| append a `ToolMessage` per call | the graph's tool node does it |

The server loads both. The toggle at the top of the chat picks which one answers:
**LangChain** (the hand-written loop), **LangGraph**, or **Side by side**, which
sends each question to both so you can compare. Each keeps its own conversation.
Both give the same answers with the same tool calls.

The API takes the same choice as `"impl": "loop"` or `"impl": "graph"` in the
request body; without it, `AGENT_IMPL` in `.env` decides (default `loop`).

## When it breaks

| error | cause |
|---|---|
| `Missing credentials` / `KeyError: 'AZURE_AI_ENDPOINT'` | `.env` is empty or not loaded. |
| `DeploymentNotFound` | `AZURE_AI_MODEL` must be the *deployment* name, not the model family name. |
| CORS error in the browser console | Start the UI with `npm run dev`; the Vite proxy in `vite.config.js` is what makes `/api` same-origin. |
| Model never calls the tool | The deployment does not support tool calling. |
| `Agent: Error: ...` in the chat | The backend caught an exception; the text after `Error:` is the cause. |

## Tests

```bash
.venv/bin/python -m pytest -q
```

Runs without Azure credentials: the tool talks to Open-Meteo (no key needed),
and the loop is driven with a fake model that replays scripted replies.
