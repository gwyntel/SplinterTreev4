import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.grok_cog import GrokCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = GrokCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = GrokCog(bot)
    assert cog.qualified_name == "Grok"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = GrokCog(bot)
    assert cog.get_temperature() is not None
