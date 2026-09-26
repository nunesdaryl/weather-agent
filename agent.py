import json
import os

import httpx
from dotenv import load_dotenv
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool

load_dotenv()

# WMO weather codes -> words, so "cloudy" comes from us, not the model's guess
WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy",
       45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
       56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
       65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
       73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers",
       81: "showers", 82: "heavy showers", 85: "snow showers", 86: "snow showers",
       95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


@tool
def get_weather(city: str) -> str:
    """Get the current weather and 3-day forecast for a city.

    Check the returned city and country: if it is the wrong place, call again
    with the official name (e.g. "Bengaluru", not "Bangalore")."""
    # Free Open-Meteo API, no key needed. Errors come back as strings, not
    # exceptions: a raised exception kills the loop, a string lets the model recover.
    try:
        results = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                            params={"name": city, "count": 1}, timeout=10.0).raise_for_status().json().get("results")
        if not results:
            return f"City '{city}' not found"
        place = results[0]
        data = httpx.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 3, "timezone": "auto",
        }, timeout=10.0).raise_for_status().json()
    except httpx.HTTPError as e:
        return f"Weather service unavailable: {e}"

    now, daily = data["current"], data["daily"]
    return json.dumps({
        "city": place["name"], "country": place.get("country"),
        "now": {"temp_c": now["temperature_2m"], "conditions": WMO.get(now["weather_code"], "unknown"),
                "wind_kmh": now["wind_speed_10m"]},
        "days": [{"date": d, "max_c": hi, "min_c": lo, "rain_pct": rain, "conditions": WMO.get(code, "unknown")}
                 for d, hi, lo, rain, code in zip(daily["time"], daily["temperature_2m_max"],
                                                  daily["temperature_2m_min"],
                                                  daily["precipitation_probability_max"],
                                                  daily["weather_code"])],
    })


# The Azure AI Foundry model, with our tool attached
model = AzureAIOpenAIApiChatModel(
    endpoint=os.environ["AZURE_AI_ENDPOINT"],
    credential=os.environ["AZURE_AI_API_KEY"],
    model=os.environ["AZURE_AI_MODEL"],
).bind_tools([get_weather])


SYSTEM_PROMPT = ("You are a friendly weather assistant. Call get_weather "
                 "for weather questions and answer in Celsius. For anything "
                 "else, just answer directly.")


def chat(message, history):
    messages = [SystemMessage(SYSTEM_PROMPT), *history, {"role": "user", "content": message}]
    for _ in range(5):                      # 1. cap: 5 calls
        reply = model.invoke(messages)      # 2. think
        messages.append(reply)
        if not reply.tool_calls:            # 3. stop
            return reply.text
        for call in reply.tool_calls:       # 4. act (one tool, so no name dispatch)
            messages.append(ToolMessage(get_weather.invoke(call["args"]),
                                        tool_call_id=call["id"]))
    return "Sorry, I couldn't get an answer."
