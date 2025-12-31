"""Weather tool - placeholder implementation."""


WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or location",
                },
            },
            "required": ["location"],
        },
    },
}


def get_weather(location: str) -> str:
    """Get weather for a location.

    This is a placeholder. Replace with actual weather API integration.

    Args:
        location: City or location name

    Returns:
        Weather description
    """
    # TODO: Integrate with a real weather API
    return f"The weather in {location} is currently sunny and 72 degrees Fahrenheit."
