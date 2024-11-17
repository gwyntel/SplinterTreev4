import pytest
from cogs.llama32_90b_cog import Llama3290bVisionCog

@pytest.fixture
def cog(bot):
    return Llama3290bVisionCog(bot)

def test_cog_initialization(cog):
    assert cog.name == "Llama-3.2-90B-Vision"
    assert cog.nickname == "Llama Vision"
    assert cog.model == "meta-llama/llama-3.2-90b-vision-instruct"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == True # Corrected assertion
