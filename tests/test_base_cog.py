import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.base_cog import BaseCog

@pytest.mark.asyncio
async def test_is_user_banned():
    bot = MagicMock()
    cog = BaseCog(bot, "TestCog", "TestNickname", ["trigger"], "test_model")
    cog.is_user_banned = AsyncMock(return_value=True)
    result = await cog.is_user_banned("12345")
    assert result is True

@pytest.mark.asyncio
async def test_update_bot_profile():
    bot = MagicMock()
    guild = MagicMock()
    cog = BaseCog(bot, "TestCog", "TestNickname", ["trigger"], "test_model")
    cog.update_bot_profile = AsyncMock()
    await cog.update_bot_profile(guild, "new_model")
    cog.update_bot_profile.assert_awaited_once_with(guild, "new_model")

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = BaseCog(bot, "TestCog", "TestNickname", ["trigger"], "test_model")
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None
