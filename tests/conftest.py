import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import discord
from discord.ext import commands

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create a mock API class
class MockAPI:
    def __init__(self):
        self.session = None
        self.openai_client = None
        self.db_pool = MagicMock()
        self.rate_limit_lock = asyncio.Lock()
        self.last_request_time = 0
        self.min_request_interval = 0.1

    async def setup(self):
        """Mock async initialization"""
        if not self.session:
            self.session = AsyncMock()
            self.session.close = AsyncMock()
        if not self.openai_client:
            self.openai_client = AsyncMock()

    async def call_openpipe(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "Mock response", "role": "assistant"}}]}

    async def report(self, *args, **kwargs):
        pass

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
        self.openai_client = None

@pytest.fixture(scope="function")
async def bot():
    """Create a bot instance with mocked API client."""
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)
    api_client = MockAPI()
    await api_client.setup()
    bot.api_client = api_client
    yield bot
    # Cleanup
    await bot.api_client.close()

# Mock the global API instance
import shared.api
mock_api = MockAPI()
shared.api.api = mock_api

# Cleanup fixture to handle any remaining open sessions
@pytest.fixture(autouse=True, scope="function")
async def cleanup_sessions():
    await mock_api.setup()
    yield
    await mock_api.close()
