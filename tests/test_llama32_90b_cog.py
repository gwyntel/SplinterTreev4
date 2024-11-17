import pytest
from cogs.llama32_90b_cog import Llama3290bVisionCog
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    context_cog = MagicMock()
    bot.get_cog.return_value = context_cog
    return bot

@pytest.fixture
def cog(mock_bot):
    return Llama3290bVisionCog(mock_bot)

def test_cog_initialization(cog):
    assert cog.name == "Llama-3.2-90B-Vision"
    assert cog.nickname == "Llama Vision"
    assert cog.model == "meta-llama/llama-3.2-90b-vision-instruct"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == True # Corrected assertion
