import pytest
from unittest.mock import MagicMock, AsyncMock
from cogs.router_cog import RouterCog

@pytest.fixture
def cog(event_loop):
    bot = MagicMock()
    context_cog = MagicMock()
    context_cog.get_context_messages = AsyncMock(return_value=[])
    bot.get_cog.return_value = context_cog

    # Create RouterCog instance
    cog = RouterCog(bot)
    # Run cog_load to initialize session and other async setups
    event_loop.run_until_complete(cog.cog_load())

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

    # Mock the HTTP POST request to return a dummy response
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={
        'choices': [{'message': {'content': 'Test response'}}]
    })
    cog.session.post = AsyncMock(return_value=mock_response)

    # Mock message.channel.send to assert it was called
    message.channel.send = AsyncMock()

    await cog.route_message(message)

    # Assert that a response was sent
    message.channel.send.assert_called_with('Test response')

@pytest.mark.asyncio
async def test_store_on_command(cog):
    """Test the '!store on' command."""
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.toggle_store(ctx, 'on')

    # Verify that the user setting is updated
    enabled = await cog.get_store_setting(ctx.author.id)
    assert enabled is True

    # Verify confirmation message
    ctx.send.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_off_command(cog):
    """Test the '!store off' command."""
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.toggle_store(ctx, 'off')

    # Verify that the user setting is updated
    enabled = await cog.get_store_setting(ctx.author.id)
    assert enabled is False

    # Verify confirmation message
    ctx.send.assert_called_with("Store setting disabled for you.")
