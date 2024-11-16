import pytest
from cogs.router_cog import RouterCog
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def cog(mock_bot):
    return RouterCog(mock_bot)

def test_cog_initialization(cog):
    """Test that the RouterCog is initialized with the correct values."""
    assert cog.name == "Router"
    assert cog.nickname == "Router"
    assert cog.model == "meta-llama/llama-3.2-3b-instruct:free"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == False

@pytest.mark.asyncio
async def test_generate_response(cog):
    """Test that the RouterCog generates a response, handling potential fallback logic."""
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild.id = 101112

    cog.api_client.call_openrouter = AsyncMock(return_value={'choices': [{'message': {'content': 'Test response'}}]})
    cog.context_cog.get_context_messages = AsyncMock(return_value=[])

    response = await cog.generate_response(message)

    assert response == "Test response"

@pytest.mark.asyncio
async def test_store_on_command(cog):
    """Test the !store on command to enable the store setting for a user."""
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()

    await cog.toggle_store(ctx, 'on')

    assert cog.is_store_enabled(789) is True
    ctx.send.assert_called_once_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_off_command(cog):
    """Test the !store off command to disable the store setting for a user."""
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()

    # First, enable the store setting
    cog.user_store_settings[789] = True

    await cog.toggle_store(ctx, 'off')

    assert cog.is_store_enabled(789) is False
    ctx.send.assert_called_once_with("Store setting disabled for you.")
