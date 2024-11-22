import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.help_cog import HelpCog

@pytest.mark.asyncio
async def test_help_command():
    bot = MagicMock()
    ctx = MagicMock()
    cog = HelpCog(bot)
    cog.help_command = AsyncMock()
    await cog.help_command(ctx)
    cog.help_command.assert_awaited_once_with(ctx)

@pytest.mark.asyncio
async def test_list_models_command():
    bot = MagicMock()
    ctx = MagicMock()
    cog = HelpCog(bot)
    cog.list_models_command = AsyncMock()
    await cog.list_models_command(ctx)
    cog.list_models_command.assert_awaited_once_with(ctx)

@pytest.mark.asyncio
async def test_list_agents_command():
    bot = MagicMock()
    ctx = MagicMock()
    cog = HelpCog(bot)
    cog.list_agents_command = AsyncMock()
    await cog.list_agents_command(ctx)
    cog.list_agents_command.assert_awaited_once_with(ctx)
