import pytest
from unittest.mock import AsyncMock, patch

from backend.agent import OllamaAgent, build_system_prompt


def test_build_system_prompt_lists_tools():
    prompt = build_system_prompt()
    assert "get_standings" in prompt
    assert "recommend_captain" in prompt


@pytest.mark.asyncio
async def test_chat_calls_tool_then_returns_reply():
    agent = OllamaAgent()
    with patch("backend.agent.OllamaAgent._call_ollama", new_callable=AsyncMock) as mock_llm, \
         patch("backend.tools.run_tool", new_callable=AsyncMock, return_value={"rank": 1}) as mock_tool:
        mock_llm.side_effect = [
            '{"tool": "get_manager_profile", "parameters": {"player_name": "A B"}}',
            "A B is currently ranked 1st.",
        ]
        response = await agent.chat("How is A B doing?")

    assert "ranked 1st" in response.reply
    assert len(response.tool_calls) == 1
    mock_tool.assert_awaited_once_with("get_manager_profile", {"player_name": "A B"})
