import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from discord.ext import commands
import discord
import json
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.new_cog import NewCog

class TestNewCog(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = commands.Bot(command_prefix="!")
        self.new_cog = NewCog(self.bot)
        self.new_cog.context_cog = MagicMock()
        self.new_cog.api_client = MagicMock()
        self.new_cog.api_client.call_openpipe = AsyncMock()

    async def test_initialization(self):
        self.assertEqual(self.new_cog.name, "New")
        self.assertEqual(self.new_cog.nickname, "New")
        self.assertEqual(self.new_cog.trigger_words, ['new', 'example'])
        self.assertEqual(self.new_cog.model, "openpipe:example/new-model")
        self.assertEqual(self.new_cog.provider, "openpipe")
        self.assertEqual(self.new_cog.prompt_file, "new_prompts")
        self.assertFalse(self.new_cog.supports_vision)
        self.assertEqual(self.new_cog.qualified_name, "New")

    async def test_get_temperature_with_existing_setting(self):
        self.new_cog.temperatures = {'new': 0.5}
        temperature = self.new_cog.get_temperature()
        self.assertEqual(temperature, 0.5)

    async def test_get_temperature_with_default(self):
        self.new_cog.temperatures = {}
        temperature = self.new_cog.get_temperature()
        self.assertEqual(temperature, 0.7)

    async def test_generate_response_success(self):
        # Mock API response
        self.new_cog.api_client.call_openpipe.return_value = {
            'choices': [
                {'message': {'content': 'Test response'}}
            ]
        }
        # Mock message
        message = MagicMock()
        message.content = 'Hello'
        message.channel.id = 123456789
        message.id = 987654321
        message.author.id = 111111
        message.guild.id = 222222

        # Mock context messages
        self.new_cog.context_cog.get_context_messages = AsyncMock(return_value=[])

        response = await self.new_cog.generate_response(message)
        self.assertEqual(response, 'Test response')

    async def test_generate_response_no_choices(self):
        # Mock API response with no choices
        self.new_cog.api_client.call_openpipe.return_value = {}

        # Mock message
        message = MagicMock()
        message.content = 'Hello'
        message.channel.id = 123456789
        message.id = 987654321
        message.author.id = 111111
        message.guild.id = 222222

        # Mock context messages
        self.new_cog.context_cog.get_context_messages = AsyncMock(return_value=[])

        response = await self.new_cog.generate_response(message)
        self.assertIsNone(response)

    async def test_generate_response_exception(self):
        # Mock API to raise exception
        self.new_cog.api_client.call_openpipe.side_effect = Exception("API Error")

        # Mock message
        message = MagicMock()
        message.content = 'Hello'
        message.channel.id = 123456789
        message.id = 987654321
        message.author.id = 111111
        message.guild.id = 222222

        # Mock context messages
        self.new_cog.context_cog.get_context_messages = AsyncMock(return_value=[])

        response = await self.new_cog.generate_response(message)
        self.assertIsNone(response)

if __name__ == '__main__':
    unittest.main()
