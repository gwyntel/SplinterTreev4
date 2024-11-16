import pytest
from unittest.mock import MagicMock, AsyncMock
from cogs.router_cog import RouterCog

@pytest.fixture
def cog():
    bot = MagicMock()
    bot.api_client = MagicMock()
    context_cog = MagicMock()
    context_cog.get_context_messages = AsyncMock(return_value=[])
    bot.get_cog.return_value = context_cog

    # Create RouterCog instance
    cog = RouterCog(bot)

    # Mock database methods
    cog._init_db = AsyncMock()
    cog.get_store_setting = AsyncMock(return_value=False)
    cog.set_store_setting = AsyncMock()

    return cog

@pytest.mark.asyncio
async def test_generate_response(cog):
    """Test that the RouterCog generates a response handling potential fallback logic."""
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild = MagicMock()
    message.guild.id = 101112

    cog.api_client.call_openrouter = AsyncMock(return_value={'choices': [{'message': {'content': 'Test response'}}]})

    response = await cog.generate_response(message)

    # Since _generate_response now yields "Test response", we need to consume the generator
    response_text = ""
    async for chunk in response:
        response_text += chunk

    assert response_text == "Test response"

@pytest.mark.asyncio
async def test_store_on_command(cog):
    """Test the !store on command to enable the store setting for a user."""
    # Create context mock
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()

    # Test store on command
    option = "on"
    await cog.toggle_store.callback(cog, ctx, option)

    # Verify the database was updated
    cog.set_store_setting.assert_called_once_with(789, True)
    ctx.send.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_off_command(cog):
    """Test the !store off command to disable the store setting for a user."""
    # Create context mock
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()

    # Test store off command
    option = "off"
    await cog.toggle_store.callback(cog, ctx, option)

    # Verify the database was updated
    cog.set_store_setting.assert_called_once_with(789, False)
    ctx.send.assert_called_with("Store setting disabled for you.")
