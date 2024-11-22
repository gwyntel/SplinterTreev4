import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
import discord
from cogs.router_cog import RouterCog
import json
import os
import asyncio

@pytest.fixture
def reset_activated_channels():
    """Fixture to reset the activated_channels state before each test."""
    with patch('cogs.router_cog.RouterCog._load_activated_channels', return_value={}):
        yield

@pytest.mark.asyncio
async def test_generate_response(reset_activated_channels):
    """Test that the router cog can generate responses."""
    # Create a mock bot
    bot = MagicMock()
    
    # Create a mock message
    message = MagicMock()
    message.content = "Hello"
    message.author.id = "123"
    message.channel.id = "456"
    message.guild.id = "789"
    message.channel.send = AsyncMock()
    message.channel.type = discord.ChannelType.text  # Not a DM
    
    # Create the cog
    cog = RouterCog(bot)
    
    # Set up activated channels
    cog.activated_channels = {
        "789": {  # guild_id
            "456": True  # channel_id
        }
    }
    
    # Create a mock cog that will be returned
    mock_cog = MagicMock()
    mock_cog.handle_message = AsyncMock()
    bot.get_cog.return_value = mock_cog
    
    # Mock the API call
    with patch('shared.api.api.call_openpipe', new_callable=AsyncMock) as mock_api:
        mock_api.return_value = {
            'choices': [{
                'message': {
                    'content': 'Mixtral'
                }
            }]
        }
        
        # Test the response generation
        await cog.handle_message(message)
        
        # Verify the mock cog's handle_message was called
        bot.get_cog.assert_called_once_with("MixtralCog")
        mock_cog.handle_message.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_activate_command_slash(reset_activated_channels):
    """Test the activate command with slash command."""
    bot = MagicMock()
    ctx = MagicMock(discord.Interaction)
    ctx.channel.id = 123
    ctx.guild.id = 456
    ctx.user.guild_permissions.administrator = True
    ctx.response.send_message = AsyncMock()
    
    cog = RouterCog(bot)
    cog.send_response = AsyncMock()
    
    await cog.activate_command.callback(cog, ctx)
    
    cog.send_response.assert_called_once_with(ctx, "✅ Bot activated in this channel.")
