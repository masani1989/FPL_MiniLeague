"""Ollama-powered agent with a tool-calling loop."""
import json
import re

import httpx

from backend import config
from backend.models import ChatResponse
from backend.tools import TOOLS, run_tool
import backend.tools as _tools


SYSTEM_PROMPT_TEMPLATE = """You are the Fantasy Kings AI assistant for a private FPL mini-league.
You have access to the following tools. To use a tool, output ONLY a JSON object in this exact format:
{{"tool": "TOOL_NAME", "parameters": {{"param": "value"}}}}

Available tools:
{tools}

Rules:
- If the user asks for standings, winnings, a manager profile, comparisons, transfer/captain advice, team evaluation, or finish probability, call the relevant tool first.
- After you receive a tool result, answer in a friendly, concise way using the data.
- Never make up numbers. If data is missing, say so.
- For group chats, keep replies short. For private chats, you may be more detailed.
"""


def build_system_prompt() -> str:
    tool_lines = []
    for t in TOOLS:
        params = ", ".join(f"{k} ({v})" for k, v in t["parameters"].items())
        tool_lines.append(f"- {t['name']}: {t['description']} Params: {params}")
    return SYSTEM_PROMPT_TEMPLATE.format(tools="\n".join(tool_lines))


class OllamaAgent:
    def __init__(self, base_url: str = config.OLLAMA_BASE_URL, model: str = config.OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.system_prompt = build_system_prompt()
        self.history: list[dict] = []

    async def _call_ollama(self, messages: list[dict]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")

    def _extract_tool_call(self, text: str) -> dict | None:
        for i, ch in enumerate(text):
            if ch != "{":
                continue
            depth = 0
            for j, inner in enumerate(text[i:], start=i):
                if inner == "{":
                    depth += 1
                elif inner == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        if '"tool"' in candidate:
                            try:
                                return json.loads(candidate)
                            except json.JSONDecodeError:
                                break
                        break
        return None

    async def chat(self, message: str, chat_id: str | None = None) -> ChatResponse:
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": message},
        ]
        tool_calls = []
        for _ in range(3):
            response_text = await self._call_ollama(messages)
            tool_call = self._extract_tool_call(response_text)
            if tool_call is None:
                # No tool call; this is the final answer.
                self.history.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ])
                if len(self.history) > 20:
                    self.history = self.history[-20:]
                return ChatResponse(reply=response_text.strip(), tool_calls=tool_calls)

            tool_calls.append(tool_call)
            result = await _tools.run_tool(tool_call.get("tool"), tool_call.get("parameters", {}))
            messages.append({"role": "assistant", "content": json.dumps(tool_call)})
            messages.append({"role": "tool", "content": json.dumps(result)})

        final = await self._call_ollama(messages)
        return ChatResponse(reply=final.strip(), tool_calls=tool_calls)
