import pytest
from cogs.grok_cog import GrokCog
from unittest.mock import MagicMock

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.api_client = MagicMock()  # Mock the api_client
    context_cog = MagicMock()
    bot.get_cog.return_value = context_cog
    return bot

@pytest.fixture
def cog(mock_bot):
    return GrokCog(mock_bot)

def test_cog_initialization(cog):
    assert cog.name == "Grok"
    assert cog.nickname == "Grok Beta"
    assert cog.model == "x-ai/grok-beta"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == True
