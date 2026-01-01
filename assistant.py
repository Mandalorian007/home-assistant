"""LLM assistant with tool support."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from tools import TOOLS, execute_tool

DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = """
You are a helpful voice assistant.

## Response Style
- Keep responses concise and conversational
- Responses will be spoken aloud, so avoid markdown, bullet points, or text-only formatting

## Input Context
You receive transcribed speech from a speech-to-text system. Transcriptions may contain:
- Phonetic errors (words that sound similar to what was said)
- Missing or extra words
- Misheard proper nouns or technical terms

Be tolerant of these errors and focus on understanding the user's intent. If a request
is unclear but you can reasonably infer the meaning, proceed with your best interpretation.
If you genuinely cannot understand what the user is asking, briefly explain that you didn't
catch that and ask them to rephrase.

## Current Time
{timestamp}

## History
If the user asks about previous conversations, references something discussed before,
or asks "what did I ask earlier", use the GetHistory tool to look up past interactions.
""".strip()


@dataclass
class ConversationResult:
    """Result of processing a user message."""

    user_input: str
    final_response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def get_system_prompt() -> str:
    """Generate system prompt with current timestamp."""
    now = datetime.now()
    timestamp = now.strftime("%A, %B %d, %Y at %I:%M %p")
    return SYSTEM_PROMPT.format(timestamp=timestamp)


def process_message(
    client: OpenAI,
    user_message: str,
    model: str = DEFAULT_MODEL,
) -> ConversationResult:
    """Process a user message and return the conversation result.

    Handles the tool execution loop internally.

    Args:
        client: OpenAI client instance
        user_message: Transcribed user speech
        model: Model to use for chat completion

    Returns:
        ConversationResult with user input, response, and tool calls
    """
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_message},
    ]
    tracked_tool_calls: list[dict[str, Any]] = []

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

        # No tool calls - return the result
        if not message.tool_calls:
            return ConversationResult(
                user_input=user_message,
                final_response=message.content or "",
                tool_calls=tracked_tool_calls,
            )

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

            # Track tool call for history
            tracked_tool_calls.append({
                "name": name,
                "arguments": args,
                "result": result,
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
