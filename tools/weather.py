"""Weather tool."""

from pydantic import BaseModel, Field
from tools.base import tool


class GetWeather(BaseModel):
    """Get the current weather for a location."""

    location: str = Field(description="City name or location")


@tool(GetWeather)
def get_weather(params: GetWeather) -> str:
    """TODO: Integrate with a real weather API."""
    return f"The weather in {params.location} is currently sunny and 72 degrees Fahrenheit."
