import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from discord import DMChannel
from cogs.router_cog import RouterCog

@pytest.mark.asyncio
async def test_handle_message_routing_to_cog(mock_session):
    # Setup
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = AsyncMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.author.bot = False
    
    # Create a proper async context manager for typing
    typing_cm = AsyncMock()
    typing_cm.__aenter__.return_value = None
    typing_cm.__aexit__.return_value = None
    message.channel.typing.return_value = typing_cm
    message.channel.send = AsyncMock()

    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value.__aiter__.return_value = ["<modelCog>GPT4O</modelCog> <debugComment>Blah</debugComment>"]
    mock_api.session = mock_session

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"

    hermes_cog = MagicMock()
    hermes_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = hermes_cog

    # Test both direct handle_message and on_message event
    await cog.handle_message(message)
    await cog.on_message(message)

    # Verify both calls worked
    assert mock_api.call_openpipe.call_count == 2
    assert hermes_cog.handle_message.call_count == 2

@pytest.mark.asyncio
async def test_handle_message_cog_not_found(mock_session):
    # Setup
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = AsyncMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.author.bot = False
    
    # Create a proper async context manager for typing
    typing_cm = AsyncMock()
    typing_cm.__aenter__.return_value = None
    typing_cm.__aexit__.return_value = None
    message.channel.typing.return_value = typing_cm
    message.channel.send = AsyncMock()

    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value.__aiter__.return_value = ["<modelCog>NonExistentCog</modelCog>"]
    mock_api.session = mock_session

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"

    bot.get_cog.return_value = None

    # Test both direct handle_message and on_message event
    await cog.handle_message(message)
    await cog.on_message(message)

    # Verify both calls worked
    assert mock_api.call_openpipe.call_count == 2
    assert message.channel.send.call_count == 2
    message.channel.send.assert_called_with("❌ Unable to route message to the appropriate module.")

@pytest.mark.asyncio
async def test_handle_message_xml_response(mock_session):
    # Setup
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = AsyncMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.author.bot = False
    
    # Create a proper async context manager for typing
    typing_cm = AsyncMock()
    typing_cm.__aenter__.return_value = None
    typing_cm.__aexit__.return_value = None
    message.channel.typing.return_value = typing_cm
    message.channel.send = AsyncMock()

    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    mock_api.call_openpipe.return_value.__aiter__.return_value = ["<modelCog>GPT4O</modelCog> <debugComment>Blah</debugComment>"]
    mock_api.session = mock_session

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"

    hermes_cog = MagicMock()
    hermes_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = hermes_cog

    # Test both direct handle_message and on_message event
    await cog.handle_message(message)
    await cog.on_message(message)

    # Verify both calls worked
    assert mock_api.call_openpipe.call_count == 2
    assert hermes_cog.handle_message.call_count == 2

@pytest.mark.asyncio
async def test_bot_message_ignored(mock_session):
    # Setup
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = AsyncMock(spec=DMChannel)
    message.author.bot = True  # This is a bot message
    message.channel.send = AsyncMock()
    
    cog = RouterCog(bot)
    
    # Test on_message event with bot message
    await cog.on_message(message)
    
    # Verify no processing occurred
    assert not message.channel.typing.called
    assert not message.channel.send.called

@pytest.mark.asyncio
async def test_guild_message_handling(mock_session):
    # Setup
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = AsyncMock()
    message.channel.id = 12345
    message.guild = AsyncMock()
    message.guild.id = 67890
    message.author = AsyncMock()
    message.author.bot = False
    message.mentions = []  # No mentions
    message.channel.send = AsyncMock()

    # Create a proper async context manager for typing
    typing_cm = AsyncMock()
    typing_cm.__aenter__.return_value = None
    typing_cm.__aexit__.return_value = None
    message.channel.typing.return_value = typing_cm

    # Setup API mock with proper async iterator
    mock_api = AsyncMock()
    mock_api.call_openpipe = AsyncMock()
    response_iter = AsyncMock()
    response_iter.__aiter__.return_value = ["<modelCog>GPT4O</modelCog>"].__aiter__()
    mock_api.call_openpipe.return_value = response_iter
    mock_api.session = mock_session

    cog = RouterCog(bot)
    cog.api_client = mock_api
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {
        "67890": {  # guild_id
            "12345": True  # channel_id
        }
    }

    hermes_cog = AsyncMock()
    hermes_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = hermes_cog

    # Test activated channel
    await cog.on_message(message)

    # Test non-activated channel
    message.channel.id = 99999
    await cog.on_message(message)

    # Verify only activated channel was processed
    assert message.channel.typing.call_count == 1
    assert mock_api.call_openpipe.call_count == 1
    assert hermes_cog.handle_message.call_count == 1
