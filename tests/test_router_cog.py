import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from cogs.router_cog import RouterCog

@pytest.fixture
async def cog():
    bot = MagicMock()
    context_cog = MagicMock()
    context_cog.get_context_messages = AsyncMock(return_value=[])
    bot.get_cog.return_value = context_cog

    # Create RouterCog instance
    cog = RouterCog(bot)
    # Run cog_load to initialize session and other async setups
    await cog.cog_load()
    # Initialize activated_channels
    cog.activated_channels = {}
    return cog

@pytest.mark.asyncio
async def test_generate_response(cog):
    """Test that the RouterCog generates a response handling potential fallback logic."""
    cog = await cog  # Await the fixture
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild = MagicMock()
    message.guild.id = 101112

    # Set up activated channel
    cog.activated_channels = {str(message.guild.id): {str(message.channel.id): True}}

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
async def test_store_command_no_option(cog):
    """Test the store command with no option."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.store_command(ctx)

    # Verify that current setting is displayed
    ctx.send.assert_called_with("Your store setting is currently disabled. Use '!store on' or '!store off' to change it.")

@pytest.mark.asyncio
async def test_store_command_on(cog):
    """Test the store command with 'on' option."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.store_command(ctx, 'on')

    # Verify that the user setting is updated
    enabled = await cog.get_store_setting(ctx.author.id)
    assert enabled is True

    # Verify confirmation message
    ctx.send.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_command_off(cog):
    """Test the store command with 'off' option."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.store_command(ctx, 'off')

    # Verify that the user setting is updated
    enabled = await cog.get_store_setting(ctx.author.id)
    assert enabled is False

    # Verify confirmation message
    ctx.send.assert_called_with("Store setting disabled for you.")

@pytest.mark.asyncio
async def test_store_command_invalid_option(cog):
    """Test the store command with invalid option."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.store_command(ctx, 'invalid')

    # Verify error message
    ctx.send.assert_called_with("Invalid option. Use '!store on' or '!store off'.")

@pytest.mark.asyncio
async def test_activate_command(cog):
    """Test the activate command."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.guild.id = 101112
    ctx.channel.id = 123
    ctx.send = AsyncMock()
    ctx.author.guild_permissions.administrator = True

    # Mock _save_activated_channels
    cog._save_activated_channels = MagicMock()

    await cog.activate_command(ctx)

    # Verify channel is activated
    assert str(ctx.guild.id) in cog.activated_channels
    assert str(ctx.channel.id) in cog.activated_channels[str(ctx.guild.id)]

    # Verify confirmation message
    ctx.send.assert_called_with("Bot activated in this channel.")

@pytest.mark.asyncio
async def test_deactivate_command(cog):
    """Test the deactivate command."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.guild.id = 101112
    ctx.channel.id = 123
    ctx.send = AsyncMock()
    ctx.author.guild_permissions.administrator = True

    # Set up pre-activated channel
    cog.activated_channels = {str(ctx.guild.id): {str(ctx.channel.id): True}}
    cog._save_activated_channels = MagicMock()

    await cog.deactivate_command(ctx)

    # Verify channel is deactivated
    assert str(ctx.channel.id) not in cog.activated_channels.get(str(ctx.guild.id), {})

    # Verify confirmation message
    ctx.send.assert_called_with("Bot deactivated in this channel.")

@pytest.mark.asyncio
async def test_uptime_command(cog):
    """Test the uptime command."""
    cog = await cog  # Await the fixture
    ctx = MagicMock()
    ctx.send = AsyncMock()

    # Set a fixed start time for testing
    cog.start_time = datetime.now(timezone.utc) - timedelta(days=1, hours=2, minutes=30, seconds=15)

    await cog.uptime_command(ctx)

    # Verify uptime message format
    ctx.send.assert_called_once()
    call_args = ctx.send.call_args[0][0]
    assert "Bot has been running for" in call_args
    assert "1 day" in call_args
    assert "2 hours" in call_args
    assert "30 minutes" in call_args
    assert "15 seconds" in call_args

@pytest.mark.asyncio
async def test_route_message_inactive_channel(cog):
    """Test that messages in inactive channels are ignored."""
    cog = await cog  # Await the fixture
    message = MagicMock()
    message.guild = MagicMock()
    message.guild.id = 101112
    message.channel.id = 123
    message.channel.send = AsyncMock()

    # Ensure channel is not activated
    cog.activated_channels = {}

    await cog.route_message(message)

    # Verify no response was sent
    message.channel.send.assert_not_called()
