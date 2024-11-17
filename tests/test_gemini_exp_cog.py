import pytest
from cogs.gemini_exp_cog import GeminiExpCog
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def cog(mock_bot):
    return GeminiExpCog(mock_bot)

def test_cog_initialization(cog):
    assert cog.name == "GeminiExp"
    assert cog.nickname == "GeminiExp"
    assert cog.model == "google/gemini-exp-1114"
    assert cog.provider == "openrouter"
    assert cog.supports_vision == True
    assert cog.trigger_words == ['geminiexp']

@pytest.mark.asyncio
async def test_generate_response(cog):
    message = MagicMock()
    message.content = "Test message"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild.id = 101112
    message.attachments = []
    message.embeds = []

    cog.api_client.call_openpipe = AsyncMock(return_value="response_stream")
    cog.context_cog.get_context_messages = AsyncMock(return_value=[])

    response = await cog.generate_response(message)
    assert response == "response_stream"

@pytest.mark.asyncio
async def test_generate_response_with_images(cog):
    message = MagicMock()
    message.content = "Test message with image"
    message.channel.id = 123
    message.id = 456
    message.author.id = 789
    message.guild.id = 101112
    
    # Mock an image attachment
    attachment = MagicMock()
    attachment.content_type = "image/jpeg"
    attachment.url = "http://example.com/test.jpg"
    message.attachments = [attachment]
    
    # Mock an embed with image
    embed = MagicMock()
    embed.image = MagicMock()
    embed.image.url = "http://example.com/embed.jpg"
    embed.thumbnail = None
    message.embeds = [embed]

    cog.api_client.call_openpipe = AsyncMock(return_value="response_stream")
    cog.context_cog.get_context_messages = AsyncMock(return_value=[])

    response = await cog.generate_response(message)
    assert response == "response_stream"

def test_get_temperature(cog):
    # Test default temperature
    assert cog.get_temperature() == 0.7

    # Test custom temperature
    cog.temperatures = {"geminiexp": 0.8}
    assert cog.get_temperature() == 0.8
