"""LLM assistant with tool support."""

import json
from datetime import datetime
from typing import cast
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from tools import TOOLS, execute_tool

DEFAULT_MODEL = "gpt-4o"


def get_system_prompt() -> str:
    """Generate system prompt with current timestamp."""
    now = datetime.now()
    timestamp = now.strftime("%A, %B %d, %Y at %I:%M %p")

    return f"""You are a helpful voice assistant. Keep responses concise and conversational since they will be spoken aloud. Avoid markdown formatting, bullet points, or other text-only constructs.

Current time: {timestamp}"""


def process_message(
    client: OpenAI,
    user_message: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Process a user message and return the assistant response.

    Handles the tool execution loop internally.

    Args:
        client: OpenAI client instance
        user_message: Transcribed user speech
        model: Model to use for chat completion

    Returns:
        Final text response to speak
    """
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_message},
    ]

    while True:
        kwargs: dict = {
            "model": model,
            "messages": messages,
        }
        if TOOLS:
            kwargs["tools"] = TOOLS

        response = client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

        choice = response.choices[0]
        message = choice.message

        # No tool calls - return the response
        if not message.tool_calls:
            return message.content or ""

        # Add assistant message with tool calls
        tool_calls = cast(list[ChatCompletionMessageToolCall], message.tool_calls)
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })

        # Execute each tool and add results
        for tool_call in tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"[Tool: {name}]", flush=True)
            result = execute_tool(name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
