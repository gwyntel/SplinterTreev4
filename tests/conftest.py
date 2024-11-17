import sys
import os
import pytest
from unittest.mock import AsyncMock
import discord
from discord.ext import commands

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def bot():
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.api_client = AsyncMock() # Add api_client attribute
    bot.add_cog(AsyncMock())
    return bot
