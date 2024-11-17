import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from discord import app_commands, Interaction, Object
from cogs.router_cog import RouterCog

@pytest.mark.asyncio
async def test_generate_response():
    """Test that the RouterCog generates a response handling potential fallback logic."""
    # Create bot mock that will properly handle get_cog
    bot = MagicMock()
    target_cog = MagicMock()
    target_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = target_cog
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    
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
        target_cog.handle_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_store_command_prefix():
    """Test the store command with prefix (!store)."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    # Mock methods
    cog.get_store_setting = AsyncMock(return_value=False)

    await cog.store_command.callback(cog, ctx)

    # Verify that current setting is displayed
    ctx.send.assert_called_with("Your store setting is currently disabled. Use '/store on' or '/store off' to change it.")

@pytest.mark.asyncio
async def test_store_command_slash():
    """Test the store command with slash command (/store)."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    interaction = MagicMock(spec=Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.user.id = 789

    # Mock methods
    cog.get_store_setting = AsyncMock(return_value=False)

    await cog.store_command.callback(cog, interaction)

    # Verify that current setting is displayed
    interaction.response.send_message.assert_called_with(
        "Your store setting is currently disabled. Use '/store on' or '/store off' to change it."
    )

@pytest.mark.asyncio
async def test_store_command_on_prefix():
    """Test the store command with 'on' option using prefix."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    ctx = MagicMock()
    ctx.author.id = 789
    ctx.send = AsyncMock()
    ctx.command.name = 'store'
    ctx.guild = None  # Simulate DM

    # Mock methods
    cog.get_store_setting = AsyncMock(return_value=True)
    cog.set_store_setting = AsyncMock()

    await cog.store_command.callback(cog, ctx, 'on')

    # Verify that the user setting is updated
    cog.set_store_setting.assert_called_with(ctx.author.id, True)
    ctx.send.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_store_command_on_slash():
    """Test the store command with 'on' option using slash command."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    interaction = MagicMock(spec=Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.user.id = 789

    # Mock methods
    cog.get_store_setting = AsyncMock(return_value=True)
    cog.set_store_setting = AsyncMock()

    await cog.store_command.callback(cog, interaction, 'on')

    # Verify that the user setting is updated
    cog.set_store_setting.assert_called_with(interaction.user.id, True)
    interaction.response.send_message.assert_called_with("Store setting enabled for you.")

@pytest.mark.asyncio
async def test_activate_command_prefix():
    """Test the activate command with prefix."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    cog.activated_channels = {}
    
    ctx = MagicMock()
    ctx.guild.id = 101112
    ctx.channel.id = 123
    ctx.send = AsyncMock()
    ctx.author.guild_permissions.administrator = True

    # Mock methods
    cog._save_activated_channels = MagicMock()

    await cog.activate_command.callback(cog, ctx)

    # Verify channel is activated
    assert str(ctx.guild.id) in cog.activated_channels
    assert str(ctx.channel.id) in cog.activated_channels[str(ctx.guild.id)]

    # Verify confirmation message with emoji
    ctx.send.assert_called_with("✅ Bot activated in this channel.")

@pytest.mark.asyncio
async def test_activate_command_slash():
    """Test the activate command with slash command."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    cog.activated_channels = {}
    
    interaction = MagicMock(spec=Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.guild_id = 101112
    interaction.channel_id = 123
    interaction.user.guild_permissions.administrator = True
    interaction.guild = MagicMock()
    interaction.guild.id = interaction.guild_id
    interaction.channel = MagicMock()
    interaction.channel.id = interaction.channel_id

    # Mock methods
    cog._save_activated_channels = MagicMock()

    await cog.activate_command.callback(cog, interaction)

    # Verify channel is activated
    assert str(interaction.guild_id) in cog.activated_channels
    assert str(interaction.channel_id) in cog.activated_channels[str(interaction.guild_id)]

    # Verify confirmation message with emoji
    interaction.response.send_message.assert_called_with("✅ Bot activated in this channel.")

@pytest.mark.asyncio
async def test_deactivate_command_prefix():
    """Test the deactivate command with prefix."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
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

    # Verify confirmation message with emoji
    ctx.send.assert_called_with("✅ Bot deactivated in this channel.")

@pytest.mark.asyncio
async def test_deactivate_command_slash():
    """Test the deactivate command with slash command."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    interaction = MagicMock(spec=Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.guild_id = 101112
    interaction.channel_id = 123
    interaction.user.guild_permissions.administrator = True
    interaction.guild = MagicMock()
    interaction.guild.id = interaction.guild_id
    interaction.channel = MagicMock()
    interaction.channel.id = interaction.channel_id

    # Set up pre-activated channel
    cog.activated_channels = {str(interaction.guild_id): {str(interaction.channel_id): True}}
    cog._save_activated_channels = MagicMock()

    await cog.deactivate_command.callback(cog, interaction)

    # Verify channel is deactivated
    assert str(interaction.channel_id) not in cog.activated_channels.get(str(interaction.guild_id), {})

    # Verify confirmation message with emoji
    interaction.response.send_message.assert_called_with("✅ Bot deactivated in this channel.")

@pytest.mark.asyncio
async def test_uptime_command_prefix():
    """Test the uptime command with prefix."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
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
async def test_uptime_command_slash():
    """Test the uptime command with slash command."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    interaction = MagicMock(spec=Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)

    # Set a fixed start time for testing
    cog.start_time = datetime.now(timezone.utc) - timedelta(days=1, hours=2, minutes=30, seconds=15)

    await cog.uptime_command.callback(cog, interaction)

    # Verify uptime message format
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args[0][0]
    assert "Bot has been running for" in call_args
    assert "1 day" in call_args
    assert "2 hours" in call_args
    assert "30 minutes" in call_args
    assert "15 seconds" in call_args

@pytest.mark.asyncio
async def test_route_message_inactive_channel():
    """Test that messages in inactive channels are ignored."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
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

@pytest.mark.asyncio
async def test_cog_load():
    """Test that slash commands are synced when the cog is loaded."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    cog = RouterCog(bot)
    
    await cog.cog_load()
    cog.bot.tree.sync.assert_called_once()
