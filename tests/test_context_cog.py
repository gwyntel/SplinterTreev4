import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.context_cog import ContextCog

@pytest.mark.asyncio
async def test_get_context_command():
    bot = MagicMock()
    ctx = MagicMock()
    cog = ContextCog(bot)
    cog.get_context_command = AsyncMock()
    await cog.get_context_command(ctx)
    cog.get_context_command.assert_awaited_once_with(ctx)

@pytest.mark.asyncio
async def test_clear_context_command():
    bot = MagicMock()
    ctx = MagicMock()
    cog = ContextCog(bot)
    cog.clear_context_command = AsyncMock()
    await cog.clear_context_command(ctx, hours=2)
    cog.clear_context_command.assert_awaited_once_with(ctx, hours=2)

@pytest.mark.asyncio
async def test_get_context_messages():
    bot = MagicMock()
    cog = ContextCog(bot)
    cog.get_context_messages = AsyncMock(return_value=[])
    messages = await cog.get_context_messages("channel_id", limit=10)
    assert messages == []
