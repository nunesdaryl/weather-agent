"""The same agent as agent.py, but LangGraph runs the loop instead of us.

create_agent builds the graph  model -> tools -> model -> ...  and stops when
the model replies without tool calls: the think / act / stop / repeat steps
that agent.py writes out by hand.
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

from agent import SYSTEM_PROMPT, get_weather  # same tool and prompt, so the comparison is fair

load_dotenv()

# Unbound model: create_agent attaches the tools itself
model = AzureAIOpenAIApiChatModel(
    endpoint=os.environ["AZURE_AI_ENDPOINT"],
    credential=os.environ["AZURE_AI_API_KEY"],
    model=os.environ["AZURE_AI_MODEL"],
)


def build_agent(model):
    return create_agent(
        model=model,
        tools=[get_weather],
        system_prompt=SYSTEM_PROMPT,
        # the cap: 5 model calls, like range(5) in agent.py
        middleware=[ModelCallLimitMiddleware(run_limit=5, exit_behavior="error")],
    )


agent = build_agent(model)


def chat(message, history):
    # No checkpointer: the UI sends the whole history on every request, as in agent.py
    try:
        result = agent.invoke({"messages": [*history, {"role": "user", "content": message}]})
    except ModelCallLimitExceededError:
        return "Sorry, I couldn't get an answer."
    return result["messages"][-1].text
