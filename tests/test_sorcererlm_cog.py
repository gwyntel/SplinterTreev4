import pytest
from cogs.sorcererlm_cog import SorcererLMCog
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def cog(mock_bot):
    return SorcererLMCog(mock_bot)

def test_cog_initialization(cog):
    assert cog.name == "SorcererLM"
    assert cog.nickname == "SorcererLM"
    assert cog.model == "raifle/sorcererlm-8x22b"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == False
    assert cog.trigger_words == ['sorcererlm']

@pytest.mark.asyncio
async def test_generate_response(cog):
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild.id = 101112

    cog.api_client.call_openpipe = AsyncMock(return_value="response_stream")
    cog.context_cog.get_context_messages = AsyncMock(return_value=[])

    response = await cog.generate_response(message)
    assert response == "response_stream"

def test_get_temperature(cog):
    # Test default temperature
    assert cog.get_temperature() == 0.7

    # Test custom temperature
    cog.temperatures = {"sorcererlm": 0.8}
    assert cog.get_temperature() == 0.8

@pytest.mark.asyncio
async def test_generate_response_with_history(cog):
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild.id = 101112

    # Mock history messages
    history = [
        {"is_assistant": True, "content": "Previous assistant message", "user_id": "bot"},
        {"is_assistant": False, "content": "Previous user message", "user_id": "user"},
        {"is_assistant": False, "content": "[SUMMARY] Context summary", "user_id": "SYSTEM"}
    ]
    
    cog.api_client.call_openpipe = AsyncMock(return_value="response_stream")
    cog.context_cog.get_context_messages = AsyncMock(return_value=history)

    response = await cog.generate_response(message)
    assert response == "response_stream"
