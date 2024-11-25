import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from cogs.router_cog import RouterCog
import discord

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user = MagicMock(id=12345)
    return bot

@pytest.fixture
def mock_message(mock_bot):
    message = MagicMock()
    message.content = "Test message"
    message.id = 1
    message.channel = MagicMock()
    message.channel.typing = MagicMock(return_value=AsyncMock())
    message.channel.send = AsyncMock()
    message.author = MagicMock(bot=False, id=67890)
    message.mentions = []
    message.guild = None
    return message

@pytest.fixture
def mock_api():
    mock_api = AsyncMock()
    
    # Create a mock async iterator for streaming
    async def mock_stream():
        yield "<modelCog>GPT4O</modelCog>"
    
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value = mock_stream()
    
    return mock_api

@pytest.mark.asyncio
async def test_route_message_basic_flow(mock_bot, mock_message, mock_api):
    # Patch the typing context manager to avoid async issues
    with patch.object(mock_message.channel, 'typing', return_value=AsyncMock()):
        # Mock cog routing
        gpt4o_cog = MagicMock()
        gpt4o_cog.handle_message = AsyncMock()
        mock_bot.get_cog.return_value = gpt4o_cog

        # Create RouterCog instance
        cog = RouterCog(mock_bot)
        cog.api_client = mock_api
        cog.router_system_prompt = "System prompt: {user_message}"

        # Execute route_message
        await cog.route_message(mock_message)

        # Verify interactions
        mock_api.call_openpipe.assert_called_once()
        gpt4o_cog.handle_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_on_message_dm_flow(mock_bot, mock_message, mock_api):
    # Configure message as DM
    mock_message.channel = MagicMock(spec=discord.DMChannel)
    mock_message.channel.typing = MagicMock(return_value=AsyncMock())

    # Patch the typing context manager to avoid async issues
    with patch.object(mock_message.channel, 'typing', return_value=AsyncMock()):
        # Mock cog routing
        gpt4o_cog = MagicMock()
        gpt4o_cog.handle_message = AsyncMock()
        mock_bot.get_cog.return_value = gpt4o_cog

        # Create RouterCog instance
        cog = RouterCog(mock_bot)
        cog.api_client = mock_api
        cog.router_system_prompt = "System prompt: {user_message}"

        # Execute on_message
        await cog.on_message(mock_message)

        # Verify interactions
        mock_api.call_openpipe.assert_called_once()
        gpt4o_cog.handle_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_route_message_bot_mention(mock_bot, mock_message, mock_api):
    # Add bot mention
    mock_message.mentions = [mock_bot.user]

    # Patch the typing context manager to avoid async issues
    with patch.object(mock_message.channel, 'typing', return_value=AsyncMock()):
        # Mock cog routing
        gpt4o_cog = MagicMock()
        gpt4o_cog.handle_message = AsyncMock()
        mock_bot.get_cog.return_value = gpt4o_cog

        # Create RouterCog instance
        cog = RouterCog(mock_bot)
        cog.api_client = mock_api
        cog.router_system_prompt = "System prompt: {user_message}"

        # Execute route_message
        await cog.route_message(mock_message)

        # Verify interactions
        mock_api.call_openpipe.assert_called_once()
        gpt4o_cog.handle_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_route_message_api_error(mock_bot, mock_message, mock_api):
    # Simulate API error
    mock_api.call_openpipe.side_effect = Exception("API Error")

    # Patch the typing context manager to avoid async issues
    with patch.object(mock_message.channel, 'typing', return_value=AsyncMock()):
        # Mock fallback cog
        gpt4o_cog = MagicMock()
        gpt4o_cog.handle_message = AsyncMock()
        
        def get_cog(name):
            if name == "GPT4OCog":
                return gpt4o_cog
            return None
            
        mock_bot.get_cog = MagicMock(side_effect=get_cog)

        # Create RouterCog instance
        cog = RouterCog(mock_bot)
        cog.api_client = mock_api
        cog.router_system_prompt = "System prompt: {user_message}"

        # Execute route_message
        await cog.route_message(mock_message)

        # Verify fallback mechanism
        mock_message.channel.send.assert_called_once()
        mock_bot.get_cog.assert_called_with("GPT4OCog")
        gpt4o_cog.handle_message.assert_not_called()  # Error message is sent instead

@pytest.mark.asyncio
async def test_route_message_multiple_cogs(mock_bot, mock_message, mock_api):
    # Setup mock streaming response with different cog
    async def mock_stream():
        yield "<modelCog>Hermes</modelCog>"
    mock_api.call_openpipe.return_value = mock_stream()

    # Patch the typing context manager to avoid async issues
    with patch.object(mock_message.channel, 'typing', return_value=AsyncMock()):
        # Mock multiple cogs
        hermes_cog = MagicMock()
        hermes_cog.handle_message = AsyncMock()
        gpt4o_cog = MagicMock()
        gpt4o_cog.handle_message = AsyncMock()
        
        def mock_get_cog(name):
            if name == 'HermesCog':
                return hermes_cog
            return gpt4o_cog
        
        mock_bot.get_cog.side_effect = mock_get_cog

        # Create RouterCog instance
        cog = RouterCog(mock_bot)
        cog.api_client = mock_api
        cog.router_system_prompt = "System prompt: {user_message}"

        # Execute route_message
        await cog.route_message(mock_message)

        # Verify interactions
        mock_api.call_openpipe.assert_called_once()
        hermes_cog.handle_message.assert_called_once_with(mock_message)
        gpt4o_cog.handle_message.assert_not_called()
