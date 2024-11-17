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
    # Initialize activated_channels
    cog.activated_channels = {}
    # Set start time
    cog.start_time = datetime.now(timezone.utc)
    # Initialize database
    await cog._setup_database()
    return cog

@pytest.mark.asyncio
async def test_generate_response():
    """Test that the RouterCog generates a response handling potential fallback logic."""
    # Create bot mock that will properly handle get_cog
    bot = MagicMock()
    target_cog = MagicMock()
    target_cog.handle_routed_message = AsyncMock()
    bot.get_cog.return_value = target_cog
    
    # Create cog instance with mocked bot
    cog = RouterCog(bot)
    cog.activated_channels = {}
    
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild = MagicMock()
    message.guild.id = 101112

    # Set up activated channel
    cog.activated_channels = {str(message.guild.id): {str(message.channel.id): True}}

    # Mock the API call to return a cog name
    mock_response = {'choices': [{'message': {'content': 'Mixtral'}}]}
    with patch('shared.api.api.call_openpipe', new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        # Mock message.channel.send to assert it was called
        message.channel.send = AsyncMock()

        # Execute the route_message method
        await cog.route_message(message)

        # Verify the API was called with correct parameters
        mock_api.assert_called_once()
        args = mock_api.call_args[1]
        assert args['model'] == 'meta-llama/llama-3.2-3b-instruct'
        assert args['user_id'] == str(message.author.id)
        assert args['guild_id'] == str(message.guild.id)

        # Verify the message was routed to the correct cog
        bot.get_cog.assert_called_once_with('MixtralCog')
        target_cog.handle_routed_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_store_command_no_option():
    """Test the store command with no option."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    # Mock get_store_setting
    cog.get_store_setting = AsyncMock(return_value=False)

    await cog.store_command.callback(cog, ctx)

    # Verify that current setting is displayed
    ctx.send.assert_called_with("Your store setting is currently disabled. Use '!store on' or '!store off' to change it.")

@pytest.mark.asyncio
async def test_store_command_on():
    """Test the store command with 'on' option."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    # Mock store setting methods
    cog.get_store_setting = AsyncMock(return_value=True)
    cog.set_store_setting = AsyncMock()

    await cog.store_command.callback(cog, ctx, 'on')

    # Verify that the user setting is updated
    cog.set_store_setting.assert_called_with(ctx.author.id, True)
    ctx.send.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_command_off():
    """Test the store command with 'off' option."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    # Mock store setting methods
    cog.get_store_setting = AsyncMock(return_value=False)
    cog.set_store_setting = AsyncMock()

    await cog.store_command.callback(cog, ctx, 'off')

    # Verify that the user setting is updated
    cog.set_store_setting.assert_called_with(ctx.author.id, False)
    ctx.send.assert_called_with("Store setting disabled for you.")

@pytest.mark.asyncio
async def test_store_command_invalid_option():
    """Test the store command with invalid option."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    await cog.store_command.callback(cog, ctx, 'invalid')

    # Verify error message
    ctx.send.assert_called_with("Invalid option. Use '!store on' or '!store off'.")

@pytest.mark.asyncio
async def test_activate_command():
    """Test the activate command."""
    cog = RouterCog(MagicMock())
    cog.activated_channels = {}
    ctx = MagicMock()
    ctx.guild.id = 101112
    ctx.channel.id = 123
    ctx.send = AsyncMock()
    ctx.author.guild_permissions.administrator = True

    # Mock _save_activated_channels
    cog._save_activated_channels = MagicMock()

    await cog.activate_command.callback(cog, ctx)

    # Verify channel is activated
    assert str(ctx.guild.id) in cog.activated_channels
    assert str(ctx.channel.id) in cog.activated_channels[str(ctx.guild.id)]

    # Verify confirmation message
    ctx.send.assert_called_with("Bot activated in this channel.")

@pytest.mark.asyncio
async def test_deactivate_command():
    """Test the deactivate command."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.guild.id = 101112
    ctx.channel.id = 123
    ctx.send = AsyncMock()
    ctx.author.guild_permissions.administrator = True

    # Set up pre-activated channel
    cog.activated_channels = {str(ctx.guild.id): {str(ctx.channel.id): True}}
    cog._save_activated_channels = MagicMock()

    await cog.deactivate_command.callback(cog, ctx)

    # Verify channel is deactivated
    assert str(ctx.channel.id) not in cog.activated_channels.get(str(ctx.guild.id), {})

    # Verify confirmation message
    ctx.send.assert_called_with("Bot deactivated in this channel.")

@pytest.mark.asyncio
async def test_uptime_command():
    """Test the uptime command."""
    cog = RouterCog(MagicMock())
    ctx = MagicMock()
    ctx.send = AsyncMock()

    # Set a fixed start time for testing
    cog.start_time = datetime.now(timezone.utc) - timedelta(days=1, hours=2, minutes=30, seconds=15)

    await cog.uptime_command.callback(cog, ctx)

    # Verify uptime message format
    ctx.send.assert_called_once()
    call_args = ctx.send.call_args[0][0]
    assert "Bot has been running for" in call_args
    assert "1 day" in call_args
    assert "2 hours" in call_args
    assert "30 minutes" in call_args
    assert "15 seconds" in call_args

@pytest.mark.asyncio
async def test_route_message_inactive_channel():
    """Test that messages in inactive channels are ignored."""
    cog = RouterCog(MagicMock())
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
