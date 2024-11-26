import pytest
import discord
from discord.ext import commands
from cogs.context_cog import ContextCog
import sqlite3
import os
import asyncio
from datetime import datetime

@pytest.fixture
def bot():
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
    return bot

@pytest.fixture
async def context_cog(bot):
    cog = ContextCog(bot)
    # Use in-memory database for testing
    cog.db_path = ':memory:'
    cog._setup_database()
    return cog

@pytest.mark.asyncio
async def test_add_message_to_context_streaming(context_cog):
    channel_id = "123"
    message_id = "456"
    guild_id = "789"
    user_id = "101112"
    
    # Simulate streaming chunks of an assistant response
    chunks = [
        "Hello",
        "Hello, how",
        "Hello, how are",
        "Hello, how are you?"
    ]
    
    # Process each chunk
    for chunk in chunks:
        await context_cog.add_message_to_context(
            message_id,
            channel_id,
            guild_id,
            user_id,
            chunk,
            is_assistant=True
        )
    
    # Verify the final stored message
    messages = await context_cog.get_context_messages(channel_id)
    assert len(messages) == 1
    assert messages[0]['content'] == "Hello, how are you?"
    assert messages[0]['is_assistant'] is True

@pytest.mark.asyncio
async def test_multiple_streaming_messages(context_cog):
    channel_id = "123"
    guild_id = "789"
    user_id = "101112"
    
    # First message stream
    message1_id = "456"
    chunks1 = [
        "First",
        "First message",
        "First message complete"
    ]
    
    # Second message stream
    message2_id = "457"
    chunks2 = [
        "Second",
        "Second message",
        "Second message complete"
    ]
    
    # Process first message chunks
    for chunk in chunks1:
        await context_cog.add_message_to_context(
            message1_id,
            channel_id,
            guild_id,
            user_id,
            chunk,
            is_assistant=True
        )
    
    # Process second message chunks
    for chunk in chunks2:
        await context_cog.add_message_to_context(
            message2_id,
            channel_id,
            guild_id,
            user_id,
            chunk,
            is_assistant=True
        )
    
    # Verify both messages are stored correctly
    messages = await context_cog.get_context_messages(channel_id)
    assert len(messages) == 2
    assert messages[0]['content'] == "First message complete"
    assert messages[1]['content'] == "Second message complete"

@pytest.mark.asyncio
async def test_interleaved_user_and_assistant_messages(context_cog):
    channel_id = "123"
    guild_id = "789"
    user_id = "101112"
    
    # User message
    await context_cog.add_message_to_context(
        "1",
        channel_id,
        guild_id,
        user_id,
        "Hello bot",
        is_assistant=False
    )
    
    # Assistant response stream
    chunks = [
        "Hi",
        "Hi there",
        "Hi there user"
    ]
    for chunk in chunks:
        await context_cog.add_message_to_context(
            "2",
            channel_id,
            guild_id,
            user_id,
            chunk,
            is_assistant=True
        )
    
    # Another user message
    await context_cog.add_message_to_context(
        "3",
        channel_id,
        guild_id,
        user_id,
        "How are you?",
        is_assistant=False
    )
    
    # Verify message sequence
    messages = await context_cog.get_context_messages(channel_id)
    assert len(messages) == 3
    assert messages[0]['content'].endswith("Hello bot")  # User message includes username prefix
    assert messages[1]['content'] == "Hi there user"
    assert messages[2]['content'].endswith("How are you?")  # User message includes username prefix
