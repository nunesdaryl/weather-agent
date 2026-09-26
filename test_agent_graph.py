"""Tests for the LangGraph version: the same checks as the loop tests in test_agent.py.

A fake chat model replays scripted replies, so no Azure credentials are needed.
"""

import os

import pytest

os.environ.setdefault("AZURE_AI_ENDPOINT", "https://example/openai/v1")
os.environ.setdefault("AZURE_AI_API_KEY", "dummy")
os.environ.setdefault("AZURE_AI_MODEL", "dummy")

import agent_graph  # noqa: E402
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402


def tool_call(city, id="call_1"):
    return {"name": "get_weather", "args": {"city": city}, "id": id, "type": "tool_call"}


class FakeModel(GenericFakeChatModel):
    """Replays scripted replies and records what it was sent."""

    calls: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.calls.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


@pytest.fixture
def fake(monkeypatch):
    def install(*replies):
        m = FakeModel(messages=iter(replies), calls=[])
        monkeypatch.setattr(agent_graph, "agent", agent_graph.build_agent(m))
        return m

    return install


def test_weather_question_thinks_acts_then_answers(fake):
    m = fake(
        AIMessage(content="", tool_calls=[tool_call("Amsterdam")]),
        AIMessage(content="Amsterdam is 19C and cloudy."),
    )
    assert agent_graph.chat("weather in amsterdam", []) == "Amsterdam is 19C and cloudy."
    assert len(m.calls) == 2, "think, act, then think again"

    tool_messages = [x for x in m.calls[1] if isinstance(x, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_1"
    assert "Amsterdam" in tool_messages[0].content


def test_non_weather_question_stops_on_the_first_reply(fake):
    m = fake(AIMessage(content="The President of India is Droupadi Murmu."))
    assert agent_graph.chat("who is the president of india", []).startswith("The President")
    assert len(m.calls) == 1, "no tool calls means the text is the answer"


def test_the_cap_stops_a_runaway_model(fake):
    runaway = AIMessage(content="", tool_calls=[tool_call("Paris", "c")])
    m = fake(*[runaway] * 50)

    assert agent_graph.chat("weather?", []) == "Sorry, I couldn't get an answer."
    assert len(m.calls) == 5, "the call limit plays the part of range(5)"


def test_messages_are_system_then_history_then_the_new_question(fake):
    m = fake(AIMessage(content="Paris is 18C."))
    agent_graph.chat("and paris?", [
        {"role": "user", "content": "amsterdam"},
        {"role": "assistant", "content": "19C cloudy"},
    ])

    sent = m.calls[0]
    assert isinstance(sent[0], SystemMessage)
    assert sent[1].content == "amsterdam"
    assert isinstance(sent[-1], HumanMessage) and sent[-1].content == "and paris?"
