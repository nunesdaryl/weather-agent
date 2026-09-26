"""Tests for the tool and the loop.

Runs without Azure credentials: the tool talks to Open-Meteo (no key needed),
and the loop is driven with a fake model that replays scripted replies.
Delete this file if you want only the five files from the slide.
"""

import json
import os

import httpx
import pytest

# agent.py builds the model at import time, so give it dummy values. Building
# the client does not touch the network; the fake model below replaces it.
os.environ.setdefault("AZURE_AI_ENDPOINT", "https://example/openai/v1")
os.environ.setdefault("AZURE_AI_API_KEY", "dummy")
os.environ.setdefault("AZURE_AI_MODEL", "dummy")

import agent  # noqa: E402
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage  # noqa: E402


def tool_call(city, id="call_1"):
    return {"name": "get_weather", "args": {"city": city}, "id": id, "type": "tool_call"}


class FakeModel:
    """Replays scripted replies and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(*replies):
        m = FakeModel(*replies)
        monkeypatch.setattr(agent, "model", m)
        return m

    return install


# --- the tool ---------------------------------------------------------------


def test_tool_metadata_is_what_the_model_sees():
    assert agent.get_weather.name == "get_weather"
    assert "weather" in agent.get_weather.description.lower()
    assert "city" in agent.get_weather.args


@pytest.mark.parametrize("city, country", [
    ("Amsterdam", "The Netherlands"), ("Paris", "France"), ("Bengaluru", "India"),
])
def test_known_city_returns_current_conditions_and_a_forecast(city, country):
    data = json.loads(agent.get_weather.invoke({"city": city}))
    assert data["country"] == country
    assert isinstance(data["now"]["temp_c"], (int, float))
    assert len(data["days"]) == 3
    # conditions are words from our WMO table, not codes for the model to guess at
    words = set(agent.WMO.values()) | {"unknown"}
    assert data["now"]["conditions"] in words
    assert all(day["conditions"] in words for day in data["days"])


def test_the_resolved_place_is_visible_so_the_model_can_catch_a_namesake():
    # Open-Meteo resolves "Bangalore" to Bangalore Town, Pakistan. The tool can't
    # fix that, but it must show where it looked so the model can retry.
    data = json.loads(agent.get_weather.invoke({"city": "Bangalore"}))
    assert data["country"] != "India"
    assert "Bengaluru" in agent.get_weather.description


def test_unknown_city_returns_a_message_rather_than_raising():
    # A raised exception would kill the loop; a string lets the model recover.
    assert agent.get_weather.invoke({"city": "zzzqqq"}) == "City 'zzzqqq' not found"


def test_network_failure_returns_a_message_rather_than_raising(monkeypatch):
    def down(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(agent.httpx, "get", down)
    assert agent.get_weather.invoke({"city": "Paris"}).startswith("Weather service unavailable")


# --- the loop ---------------------------------------------------------------


def test_weather_question_thinks_acts_then_answers(fake):
    m = fake(
        AIMessage(content="", tool_calls=[tool_call("Amsterdam")]),
        AIMessage(content="Amsterdam is 19C and cloudy."),
    )
    answer = agent.chat("weather in amsterdam", [])

    assert answer == "Amsterdam is 19C and cloudy."
    assert len(m.calls) == 2, "think, act, then think again"

    # The tool result must be fed back tagged with the id the model asked with.
    tool_messages = [x for x in m.calls[1] if isinstance(x, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_1"
    assert "Amsterdam" in tool_messages[0].content or "latitude" in tool_messages[0].content


def test_non_weather_question_stops_on_the_first_reply(fake):
    m = fake(AIMessage(content="The President of India is Droupadi Murmu."))
    answer = agent.chat("who is the president of india", [])

    assert answer.startswith("The President")
    assert len(m.calls) == 1, "no tool calls means the text is the answer"
    assert not any(isinstance(x, ToolMessage) for x in m.calls[0])


def test_the_cap_stops_a_runaway_model(fake):
    runaway = AIMessage(content="", tool_calls=[tool_call("Paris", "c")])
    m = fake(*[runaway] * 50)

    assert agent.chat("weather?", []) == "Sorry, I couldn't get an answer."
    assert len(m.calls) == 5, "the range(5) cap is what prevents an endless loop"


def test_messages_are_system_then_history_then_the_new_question(fake):
    m = fake(AIMessage(content="Paris is 18C."))
    agent.chat(
        "and paris?",
        [
            {"role": "user", "content": "amsterdam"},
            {"role": "assistant", "content": "19C cloudy"},
        ],
    )

    sent = m.calls[0]
    assert isinstance(sent[0], SystemMessage)
    assert sent[1]["content"] == "amsterdam"
    assert sent[-1] == {"role": "user", "content": "and paris?"}


# --- the route --------------------------------------------------------------


def test_route_answers_with_json_even_when_the_model_fails(monkeypatch):
    # The UI reads data.answer; a plain-text 500 would leave it hanging.
    from fastapi.testclient import TestClient

    import main

    def broken(message, history):
        raise RuntimeError("DeploymentNotFound")

    monkeypatch.setattr(main, "chat", broken)
    r = TestClient(main.app).post("/api/chat", json={"message": "hi", "history": []})
    assert r.status_code == 200
    assert r.json()["answer"] == "Error: RuntimeError: DeploymentNotFound"
