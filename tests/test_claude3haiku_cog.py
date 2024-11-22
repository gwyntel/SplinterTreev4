import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.claude3haiku_cog import Claude3HaikuCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = Claude3HaikuCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = Claude3HaikuCog(bot)
    assert cog.qualified_name == "Claude-3-Haiku"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = Claude3HaikuCog(bot)
    assert cog.get_temperature() is not None
