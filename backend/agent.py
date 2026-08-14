"""LLM agent using Ollama native /api/chat with tool support."""
import json

import httpx

from backend import config
from backend.models import ChatResponse
from backend.tools import TOOLS, run_tool


SYSTEM_PROMPT_TEMPLATE = """You are the Fantasy Kings AI assistant for a private FPL mini-league.
You have access to tools that can query mini-league data and give FPL advice.

Rules:
- If the user asks for standings, winnings, a manager profile, comparisons, transfer/captain advice, team evaluation, or finish probability, call the relevant tool first.
- After you receive a tool result, answer in a friendly, concise way using the data.
- Never make up numbers. If data is missing, say so.
- For group chats, keep replies short. For private chats, you may be more detailed.
- If the user's chat is registered to a manager, interpret ambiguous references like "my team", "me", "I", or "my" as referring to that manager.
- Do not reveal private details of other managers to a registered user unless explicitly asked.
- When the evaluate_team tool returns an auth_prompt, tell the user to run '/login <session_cookie>' in a private chat with the bot, pasting their FPL browser session cookie, so you can fetch their latest submitted team.
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE


def _normalize_tool_name(name: str) -> str:
    """Strip common namespace/prefix noise from tool names."""
    return name.split(".")[-1].strip()


def _tool_result_message(tool_call: dict, result: dict) -> dict:
    """Build a native Ollama tool result message."""
    return {
        "role": "tool",
        "content": json.dumps(result),
    }


class OllamaAgent:
    def __init__(self, base_url: str = config.OLLAMA_BASE_URL, model: str = config.OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.system_prompt = build_system_prompt()
        self.history: list[dict] = []

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        # Ollama Cloud uses an API key; local Ollama ignores auth.
        api_key = config.OLLAMA_API_KEY
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload: dict = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _extract_tool_calls(self, llm_response: dict) -> list[dict]:
        message = llm_response.get("message", {})
        return message.get("tool_calls", []) or []

    def _reply_text(self, llm_response: dict) -> str:
        message = llm_response.get("message", {})
        return message.get("content", "") or ""

    async def chat(self, message: str, chat_id: str | None = None) -> ChatResponse:
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": message},
        ]
        tool_calls_log: list[dict] = []
        for _ in range(3):
            response = await self._call_llm(messages, tools=TOOLS)
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                reply = self._reply_text(response)
                self.history.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                ])
                if len(self.history) > 20:
                    self.history = self.history[-20:]
                return ChatResponse(reply=reply.strip(), tool_calls=tool_calls_log)

            assistant_message = response.get("message", {})
            messages.append(assistant_message)
            for tool_call in tool_calls:
                tool_calls_log.append(tool_call)
                function_name = _normalize_tool_name(tool_call.get("function", {}).get("name", ""))
                arguments = tool_call.get("function", {}).get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                result = await run_tool(function_name, arguments)
                messages.append(_tool_result_message(tool_call, result))

        final_response = await self._call_llm(messages)
        return ChatResponse(reply=self._reply_text(final_response).strip(), tool_calls=tool_calls_log)
