import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import DMChannel
from cogs.router_cog import RouterCog

class AsyncContextManagerMock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_cog_check_dm_channel():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock(spec=DMChannel)
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    # Should allow commands in DM channels without permission check
    assert result is True

@pytest.mark.asyncio
async def test_cog_check_guild_channel_with_permission():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock()  # Not a DMChannel
    ctx.author.guild_permissions.manage_channels = True
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    # Should allow commands with manage_channels permission
    assert result is True

@pytest.mark.asyncio
async def test_cog_check_guild_channel_without_permission():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.channel = MagicMock()  # Not a DMChannel
    ctx.author.guild_permissions.manage_channels = False
    
    cog = RouterCog(bot)
    result = await cog.cog_check(ctx)
    
    # Should not allow commands without manage_channels permission
    assert result is False

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
    
    cog = RouterCog(bot)
    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.activate(ctx)
        
        # Verify channel was activated
        assert str(ctx.guild.id) in cog.activated_channels
        assert str(ctx.channel.id) in cog.activated_channels[str(ctx.guild.id)]
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
        await cog.activate(ctx)
        
        # Verify DM channel was activated
        assert 'DM' in cog.activated_channels
        assert str(ctx.channel.id) in cog.activated_channels['DM']
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
    
    cog = RouterCog(bot)
    # Pre-activate the channel
    guild_id = str(ctx.guild.id)
    channel_id = str(ctx.channel.id)
    cog.activated_channels = {guild_id: {channel_id: True}}
    
    with patch.object(cog, '_save_activated_channels') as mock_save:
        await cog.deactivate(ctx)
        
        # Verify channel was deactivated
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
        await cog.deactivate(ctx)
        
        # Verify DM channel was deactivated
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
    
    cog = RouterCog(bot)
    # Channel starts deactivated
    cog.activated_channels = {}
    
    await cog.deactivate(ctx)
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
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    cog = RouterCog(bot)
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}

    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_api:
        mock_api.return_value.__aiter__.return_value = iter(["Hermes"])

        hermes_cog = MagicMock()
        hermes_cog.handle_message = AsyncMock()
        bot.get_cog.return_value = hermes_cog

        await cog.handle_message(message)

        mock_api.assert_called_once()
        assert "System prompt: Test message" in mock_api.call_args[1]["messages"][0]["content"]

        bot.get_cog.assert_called_with("HermesCog")
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
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    cog = RouterCog(bot)
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}

    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_api:
        mock_api.return_value.__aiter__.return_value = iter(["NonExistentCog"])

        bot.get_cog.return_value = None

        await cog.handle_message(message)

        mock_api.assert_called_once()
        assert "System prompt: Test message" in mock_api.call_args[1]["messages"][0]["content"]

        bot.get_cog.assert_called_with("NonExistentCogCog")
        message.channel.send.assert_called_once_with("❌ Unable to route message to the appropriate module.")

@pytest.mark.asyncio
async def test_handle_message_inactive_channel():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock()
    message.channel.id = 12345
    message.guild.id = 67890
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    cog = RouterCog(bot)
    cog.activated_channels = {}  # No channels activated

    await cog.handle_message(message)
    
    # Message should be ignored (no API calls or responses)
    message.channel.send.assert_not_called()
