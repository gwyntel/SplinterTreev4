import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.wizard_cog import WizardCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = WizardCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = WizardCog(bot)
    assert cog.qualified_name == "Wizard"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = WizardCog(bot)
    assert cog.get_temperature() is not None
