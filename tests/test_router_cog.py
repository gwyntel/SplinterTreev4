import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from discord import DMChannel
from cogs.router_cog import RouterCog

@pytest.mark.asyncio
async def test_cog_check_dm_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock(spec=DMChannel)
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    assert result is True

@pytest.mark.asyncio
async def test_cog_check_guild_channel_with_permission():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock()
    ctx.channel.type = 0  # TextChannel
    ctx.author.guild_permissions.manage_channels = True
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    assert result is True

@pytest.mark.asyncio
async def test_cog_check_guild_channel_without_permission():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock()
    ctx.channel.type = 0  # TextChannel
    ctx.author.guild_permissions.manage_channels = False
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    assert result is False

@pytest.mark.asyncio
async def test_get_temperature_with_config():
    bot = MagicMock()
    cog = RouterCog(bot)
    cog.temperatures = {'router': 0.8}
    
    result = cog.get_temperature()
    assert result == 0.8

@pytest.mark.asyncio
async def test_get_temperature_without_config():
    bot = MagicMock()
    cog = RouterCog(bot)
    cog.temperatures = {}
    
    result = cog.get_temperature()
    assert result == 0.7

@pytest.mark.asyncio
async def test_activate_guild_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel.id = 12345
    ctx.guild.id = 67890
    ctx.send = AsyncMock()

    # Mock that it's not a DM channel
    ctx.channel = MagicMock()
    ctx.channel.id = 12345
    ctx.channel.__class__ = type('TextChannel', (), {'__module__': 'discord'})

    cog = RouterCog(bot)
    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.activate.callback(cog, ctx)
        
        guild_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)
        assert guild_id in cog.activated_channels
        assert channel_id in cog.activated_channels[guild_id]
        assert mock_save.called
        ctx.send.assert_called_once_with("✅ Router activated in this channel")

@pytest.mark.asyncio
async def test_activate_dm_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock(spec=DMChannel)
    ctx.channel.id = 12345
    ctx.send = AsyncMock()

    cog = RouterCog(bot)
    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.activate.callback(cog, ctx)
        
        channel_id = str(ctx.channel.id)
        assert 'DM' in cog.activated_channels
        assert channel_id in cog.activated_channels['DM']
        assert mock_save.called
        ctx.send.assert_called_once_with("✅ Router activated in this DM channel")

@pytest.mark.asyncio
async def test_deactivate_guild_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel.id = 12345
    ctx.guild.id = 67890
    ctx.send = AsyncMock()

    # Mock that it's not a DM channel
    ctx.channel = MagicMock()
    ctx.channel.id = 12345
    ctx.channel.__class__ = type('TextChannel', (), {'__module__': 'discord'})

    cog = RouterCog(bot)
    # Pre-activate the channel
    guild_id = str(ctx.guild.id)
    channel_id = str(ctx.channel.id)
    cog.activated_channels = {guild_id: {channel_id: True}}

    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.deactivate.callback(cog, ctx)
        
        assert guild_id not in cog.activated_channels
        assert mock_save.called
        ctx.send.assert_called_once_with("✅ Router deactivated in this channel")

@pytest.mark.asyncio
async def test_deactivate_dm_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock(spec=DMChannel)
    ctx.channel.id = 12345
    ctx.send = AsyncMock()

    cog = RouterCog(bot)
    # Pre-activate the DM channel
    channel_id = str(ctx.channel.id)
    cog.activated_channels = {'DM': {channel_id: True}}

    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.deactivate.callback(cog, ctx)
        
        assert 'DM' not in cog.activated_channels
        assert mock_save.called
        ctx.send.assert_called_once_with("✅ Router deactivated in this DM channel")

@pytest.mark.asyncio
async def test_deactivate_inactive_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel.id = 12345
    ctx.guild.id = 67890
    ctx.send = AsyncMock()

    # Mock that it's not a DM channel
    ctx.channel = MagicMock()
    ctx.channel.id = 12345
    ctx.channel.__class__ = type('TextChannel', (), {'__module__': 'discord'})

    cog = RouterCog(bot)
    # Channel starts deactivated
    cog.activated_channels = {}

    await cog.deactivate.callback(cog, ctx)
    ctx.send.assert_called_once_with("❌ Router is not activated in this channel")

@pytest.mark.asyncio
async def test_handle_message_routing_to_cog():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.channel.typing = AsyncMock()
    message.channel.typing.return_value.__aenter__ = AsyncMock()
    message.channel.typing.return_value.__aexit__ = AsyncMock()
    message.channel.send = AsyncMock()

    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value.__aiter__.return_value = [
        "GPT4O"
    ]

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}

    hermes_cog = MagicMock()
    hermes_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = hermes_cog

    await cog.handle_message(message)

    mock_api.call_openpipe.assert_called_once()
    bot.get_cog.assert_called_with("GPT4OCog")
    hermes_cog.handle_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_handle_message_cog_not_found():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.channel.typing = AsyncMock()
    message.channel.typing.return_value.__aenter__ = AsyncMock()
    message.channel.typing.return_value.__aexit__ = AsyncMock()
    message.channel.send = AsyncMock()

    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value.__aiter__.return_value = [
        "NonExistentCog"
    ]

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}

    bot.get_cog.return_value = None

    await cog.handle_message(message)

    mock_api.call_openpipe.assert_called_once()
    message.channel.send.assert_called_once_with("❌ Unable to route message to the appropriate module.")

@pytest.mark.asyncio
async def test_handle_message_inactive_channel():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock()
    message.channel.id = 12345
    message.guild.id = 67890
    message.channel.typing = AsyncMock()
    message.channel.typing.return_value.__aenter__ = AsyncMock()
    message.channel.typing.return_value.__aexit__ = AsyncMock()
    message.channel.send = AsyncMock()

    cog = RouterCog(bot)
    cog.activated_channels = {}  # No channels activated

    await cog.handle_message(message)

    # Should return early without calling the API
    message.channel.send.assert_not_called()
