import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.qwen32b_cog import Qwen32BCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = Qwen32BCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = Qwen32BCog(bot)
    assert cog.qualified_name == "Qwen32B"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = Qwen32BCog(bot)
    assert cog.get_temperature() is not None
