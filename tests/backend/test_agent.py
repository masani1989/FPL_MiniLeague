import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.agent import OllamaAgent, build_system_prompt


def test_build_system_prompt_contains_persona():
    prompt = build_system_prompt()
    assert "Fantasy Kings" in prompt
    assert "tools" in prompt.lower()


def _tool_response(name: str, arguments: dict) -> dict:
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "function": {"name": name, "arguments": arguments},
            }],
        },
    }


def _text_response(text: str) -> dict:
    return {"message": {"role": "assistant", "content": text}}


@pytest.mark.asyncio
async def test_chat_calls_tool_then_returns_reply():
    agent = OllamaAgent()
    with patch("backend.agent.OllamaAgent._call_llm", new_callable=AsyncMock) as mock_llm, \
         patch("backend.agent.run_tool", new_callable=AsyncMock, return_value={"rank": 1}) as mock_tool:
        mock_llm.side_effect = [
            _tool_response("get_manager_profile", {"player_name": "A B"}),
            _text_response("A B is currently ranked 1st."),
        ]
        response = await agent.chat("How is A B doing?")

    assert "ranked 1st" in response.reply
    assert len(response.tool_calls) == 1
    mock_tool.assert_awaited_once_with("get_manager_profile", {"player_name": "A B"})
