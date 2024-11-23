import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.context_cog import ContextCog
from config import DEFAULT_CONTEXT_WINDOW, MAX_CONTEXT_WINDOW

@pytest.mark.asyncio
async def test_get_context_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    await cog.get_context_command.callback(cog, ctx)
    ctx.send.assert_awaited_once_with(f"Current context window size: {DEFAULT_CONTEXT_WINDOW} messages")

@pytest.mark.asyncio
async def test_clear_context_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    await cog.clear_context_command.callback(cog, ctx, hours=2)
    ctx.send.assert_awaited_once_with("✅ Cleared messages older than 2 hours from context")

@pytest.mark.asyncio
async def test_get_context_messages():
    bot = MagicMock()
    cog = ContextCog(bot)
    messages = await cog.get_context_messages("channel_id", limit=10)
    assert isinstance(messages, list)

@pytest.mark.asyncio
async def test_setcontext_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    
    # Test valid size
    with patch('json.dump'):
        await cog.set_context_command.callback(cog, ctx, size=10)
        ctx.send.assert_awaited_once_with("✅ Context window size set to 10 messages")
    
    # Test size too small
    ctx.send.reset_mock()
    await cog.set_context_command.callback(cog, ctx, size=0)
    ctx.send.assert_awaited_once_with("❌ Context window size must be at least 1")
    
    # Test size too large
    ctx.send.reset_mock()
    await cog.set_context_command.callback(cog, ctx, size=MAX_CONTEXT_WINDOW + 1)
    ctx.send.assert_awaited_once_with(f"❌ Context window size cannot exceed {MAX_CONTEXT_WINDOW}")

@pytest.mark.asyncio
async def test_resetcontext_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    
    # Set a custom context window size first
    with patch('json.dump'):
        await cog.set_context_command.callback(cog, ctx, size=10)
        ctx.send.reset_mock()
        
        # Test resetting context
        await cog.reset_context_command.callback(cog, ctx)
        ctx.send.assert_awaited_once_with(f"✅ Context window size reset to default ({DEFAULT_CONTEXT_WINDOW} messages)")

@pytest.mark.asyncio
async def test_clear_context_command_with_hours():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    
    # Test clearing with specific hours
    await cog.clear_context_command.callback(cog, ctx, hours=24)
    ctx.send.assert_awaited_once_with("✅ Cleared messages older than 24 hours from context")

@pytest.mark.asyncio
async def test_clear_context_command_all():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.channel.id = "123"
    cog = ContextCog(bot)
    
    # Test clearing all messages
    await cog.clear_context_command.callback(cog, ctx)
    ctx.send.assert_awaited_once_with("✅ Cleared all messages from context")
