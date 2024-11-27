import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.magnum_cog import MagnumCog

@pytest.mark.asyncio
async def test_generate_response():
    bot = MagicMock()
    message = MagicMock()
    cog = MagnumCog(bot)
    cog.generate_response = AsyncMock(return_value=AsyncMock())
    response = await cog.generate_response(message)
    assert response is not None

@pytest.mark.asyncio
async def test_qualified_name():
    bot = MagicMock()
    cog = MagnumCog(bot)
    assert cog.qualified_name == "Magnum"

@pytest.mark.asyncio
async def test_get_temperature():
    bot = MagicMock()
    cog = MagnumCog(bot)
    assert cog.get_temperature() is not None

@pytest.mark.asyncio
async def test_passes_model_id_to_context():
    # Create mock bot and message
    bot = MagicMock()
    message = MagicMock()
    message.channel.id = "123"
    message.content = "Test message"
    
    # Create mock context cog
    mock_context_cog = AsyncMock()
    mock_context_cog.get_context_messages = AsyncMock(return_value=[])
    
    # Create cog instance with mocked context_cog
    cog = MagnumCog(bot)
    cog.context_cog = mock_context_cog
    cog.api_client = AsyncMock()
    
    # Call generate_response
    await cog.generate_response(message)
    
    # Verify get_context_messages was called with correct model_id
    mock_context_cog.get_context_messages.assert_called_once()
    call_args = mock_context_cog.get_context_messages.call_args[1]
    assert 'model_id' in call_args
    assert call_args['model_id'] == cog.model
    assert 'infermatic' in call_args['model_id']
