import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.gpt4o_cog import GPT4OCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = GPT4OCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = GPT4OCog(bot)
    assert cog.qualified_name == "GPT-4o"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = GPT4OCog(bot)
    assert cog.get_temperature() is not None
