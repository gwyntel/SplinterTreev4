import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord import DMChannel
from cogs.router_cog import RouterCog

class AsyncContextManagerMock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_handle_message_routing_to_cog():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)  # Properly mock DMChannel
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None  # Simulate a DM channel
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    # Mock the RouterCog
    cog = RouterCog(bot)
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}  # Correctly simulate DM activation

    # Mock the API response to route to a specific cog
    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_api:
        mock_api.return_value.__aiter__.return_value = iter(["Hermes"])

        # Mock the HermesCog
        hermes_cog = MagicMock()
        hermes_cog.handle_message = AsyncMock()
        bot.get_cog.return_value = hermes_cog

        # Call handle_message
        await cog.handle_message(message)

        # Assert the API was called with the correct prompt
        mock_api.assert_called_once()
        assert "System prompt: Test message" in mock_api.call_args[1]["messages"][0]["content"]

        # Assert the message was routed to HermesCog
        bot.get_cog.assert_called_with("HermesCog")
        hermes_cog.handle_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_handle_message_cog_not_found():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)  # Properly mock DMChannel
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None  # Simulate a DM channel
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    # Mock the RouterCog
    cog = RouterCog(bot)
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}  # Correctly simulate DM activation

    # Mock the API response to route to a non-existent cog
    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_api:
        mock_api.return_value.__aiter__.return_value = iter(["NonExistentCog"])

        # Simulate no cog found
        bot.get_cog.return_value = None

        # Call handle_message
        await cog.handle_message(message)

        # Assert the API was called with the correct prompt
        mock_api.assert_called_once()
        assert "System prompt: Test message" in mock_api.call_args[1]["messages"][0]["content"]

        # Assert the message was not routed and an error was sent
        bot.get_cog.assert_called_with("NonExistentCog")
        message.channel.send.assert_called_once_with("❌ Unable to route message to the appropriate module.")

@pytest.mark.asyncio
async def test_handle_message_cog_missing_handle_message():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)  # Properly mock DMChannel
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None  # Simulate a DM channel
    message.channel.typing = AsyncMock(return_value=AsyncContextManagerMock())
    message.channel.send = AsyncMock()

    # Mock the RouterCog
    cog = RouterCog(bot)
    cog.router_system_prompt = "System prompt: {user_message}"
    cog.activated_channels = {"DM": {"12345": True}}  # Correctly simulate DM activation

    # Mock the API response to route to a cog without handle_message
    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_api:
        mock_api.return_value.__aiter__.return_value = iter(["Hermes"])

        # Mock the HermesCog without handle_message
        hermes_cog = MagicMock()
        del hermes_cog.handle_message
        bot.get_cog.return_value = hermes_cog

        # Call handle_message
        await cog.handle_message(message)

        # Assert the API was called with the correct prompt
        mock_api.assert_called_once()
        assert "System prompt: Test message" in mock_api.call_args[1]["messages"][0]["content"]

        # Assert the message was not routed and an error was sent
        bot.get_cog.assert_called_with("HermesCog")
        message.channel.send.assert_called_once_with("❌ Unable to route message to the appropriate module.")
