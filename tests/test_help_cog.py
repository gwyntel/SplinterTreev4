import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.help_cog import HelpCog
import json
import os

@pytest.mark.asyncio
async def test_help_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    cog = HelpCog(bot)
    await cog.help_command.callback(cog, ctx)
    assert ctx.send.called

@pytest.mark.asyncio
async def test_list_models_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    cog = HelpCog(bot)
    await cog.list_models_command.callback(cog, ctx)
    assert ctx.send.called

@pytest.mark.asyncio
async def test_list_agents_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    cog = HelpCog(bot)
    await cog.list_agents_command.callback(cog, ctx)
    assert ctx.send.called

@pytest.mark.asyncio
async def test_uptime_command():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    cog = HelpCog(bot)
    
    # Mock get_uptime to return a fixed value
    with patch('cogs.help_cog.get_uptime', return_value="1d 2h 3m"):
        await cog.uptime_command.callback(cog, ctx)
        ctx.send.assert_awaited_once_with("🕒 Bot has been running for: 1d 2h 3m")

@pytest.mark.asyncio
async def test_set_system_prompt():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    agent = "TestAgent"
    prompt = "Test prompt"
    
    # Create a mock cog that will be "found" by the command
    mock_agent_cog = MagicMock()
    mock_agent_cog.name = agent
    bot.cogs.values.return_value = [mock_agent_cog]
    
    cog = HelpCog(bot)
    
    # Mock the file operations
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = '{"system_prompts": {}}'
        await cog.set_system_prompt.callback(cog, ctx, agent=agent, prompt=prompt)
        
        # Verify the prompt was set
        ctx.send.assert_awaited_once_with(f"✅ System prompt updated for {agent}")
        assert mock_agent_cog.raw_prompt == prompt

@pytest.mark.asyncio
async def test_reset_system_prompt():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    agent = "TestAgent"
    
    # Create a mock cog that will be "found" by the command
    mock_agent_cog = MagicMock()
    mock_agent_cog.name = agent
    mock_agent_cog.default_prompt = "Default prompt"
    bot.cogs.values.return_value = [mock_agent_cog]
    
    cog = HelpCog(bot)
    
    # Mock the file operations
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = '{"system_prompts": {"testagent": "Custom prompt"}}'
        await cog.reset_system_prompt.callback(cog, ctx, agent=agent)
        
        # Verify the prompt was reset
        ctx.send.assert_awaited_once_with(f"✅ System prompt reset to default for {agent}")
        assert mock_agent_cog.raw_prompt == mock_agent_cog.default_prompt

@pytest.mark.asyncio
async def test_set_system_prompt_invalid_agent():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    agent = "NonexistentAgent"
    prompt = "Test prompt"
    
    bot.cogs.values.return_value = []  # No cogs found
    
    cog = HelpCog(bot)
    await cog.set_system_prompt.callback(cog, ctx, agent=agent, prompt=prompt)
    
    # Verify error message was sent
    ctx.send.assert_awaited_once_with(f"❌ Agent '{agent}' not found")

@pytest.mark.asyncio
async def test_reset_system_prompt_invalid_agent():
    bot = MagicMock()
    ctx = MagicMock()
    ctx.send = AsyncMock()
    agent = "NonexistentAgent"
    
    bot.cogs.values.return_value = []  # No cogs found
    
    cog = HelpCog(bot)
    await cog.reset_system_prompt.callback(cog, ctx, agent=agent)
    
    # Verify error message was sent
    ctx.send.assert_awaited_once_with(f"❌ Agent '{agent}' not found")
