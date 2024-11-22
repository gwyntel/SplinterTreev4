import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.unslop_cog import UnslopCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = UnslopCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = UnslopCog(bot)
    assert cog.qualified_name == "Unslop"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = UnslopCog(bot)
    assert cog.get_temperature() is not None
