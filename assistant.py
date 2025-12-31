"""LLM assistant with tool support."""

import json
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from tools import TOOLS, execute_tool

SYSTEM_PROMPT = """You are a helpful voice assistant. Keep responses concise and conversational since they will be spoken aloud. Avoid markdown formatting, bullet points, or other text-only constructs."""

DEFAULT_MODEL = "gpt-4o"


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
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    tools: list[ChatCompletionToolParam] = [
        {"type": "function", "function": tool["function"]}
        for tool in TOOLS
    ]

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
        )

        choice = response.choices[0]
        message = choice.message

        # No tool calls - return the response
        if not message.tool_calls:
            return message.content or ""

        # Add assistant message with tool calls
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
                for tc in message.tool_calls
            ],
        })

        # Execute each tool and add results
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"Executing tool: {name}({args})")
            result = execute_tool(name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
