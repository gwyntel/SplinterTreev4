import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from discord import DMChannel
from cogs.router_cog import RouterCog

@pytest.mark.asyncio
async def test_handle_message_routing_to_cog():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.channel.typing = AsyncMock()
    message.channel.typing.return_value.__aenter__ = AsyncMock()
    message.channel.typing.return_value.__aexit__ = AsyncMock()
    message.channel.send = AsyncMock()

    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_call_openpipe:
        mock_call_openpipe.return_value.__aiter__.return_value = ["GPT4O"]

        cog = RouterCog(bot)
        cog.router_system_prompt = "System prompt: {user_message}"
        cog.activated_channels = {"DM": {"12345": True}}

        hermes_cog = MagicMock()
        hermes_cog.handle_message = AsyncMock()
        bot.get_cog.return_value = hermes_cog

        await cog.handle_message(message)

        mock_call_openpipe.assert_called_once()
        bot.get_cog.assert_called_with("GPT4OCog")
        hermes_cog.handle_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_handle_message_cog_not_found():
    bot = MagicMock()
    message = MagicMock()
    message.content = "Test message"
    message.channel = MagicMock(spec=DMChannel)
    message.channel.id = 12345
    message.author.id = 67890
    message.guild = None
    message.channel.typing = AsyncMock()
    message.channel.typing.return_value.__aenter__ = AsyncMock()
    message.channel.typing.return_value.__aexit__ = AsyncMock()
    message.channel.send = AsyncMock()

    with patch("shared.api.api.call_openpipe", new_callable=AsyncMock) as mock_call_openpipe:
        mock_call_openpipe.return_value.__aiter__.return_value = ["NonExistentCog"]

        cog = RouterCog(bot)
        cog.router_system_prompt = "System prompt: {user_message}"
        cog.activated_channels = {"DM": {"12345": True}}

        bot.get_cog.return_value = None

        await cog.handle_message(message)

        mock_call_openpipe.assert_called_once()
        message.channel.send.assert_called_once_with("❌ Unable to route message to the appropriate module.")
