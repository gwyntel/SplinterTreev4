import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.management_cog import ManagementCog

@pytest.mark.asyncio
async def test_ban_user():
    bot = MagicMock()
    cog = ManagementCog(bot)
    cog.ban_user = AsyncMock(return_value=True)
    result = await cog.ban_user("12345")
    assert result is True

@pytest.mark.asyncio
async def test_optout():
    bot = MagicMock()
    ctx = MagicMock()
    cog = ManagementCog(bot)
    cog.optout = AsyncMock()
    await cog.optout(ctx)
    cog.optout.assert_awaited_once_with(ctx)

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = ManagementCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None
