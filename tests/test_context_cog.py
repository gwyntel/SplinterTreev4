import pytest
import discord
from discord.ext import commands
from cogs.context_cog import ContextCog
import sqlite3
import os
import asyncio
from datetime import datetime
from unittest.mock import MagicMock

@pytest.fixture
def bot():
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
    bot.fetch_user = lambda x: MagicMock(display_name="TestUser")
    return bot

@pytest.fixture
def context_cog(bot):
    # Create an in-memory database
    db = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = db.cursor()
    cursor.execute('''
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_message_id TEXT UNIQUE,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        channel_id TEXT NOT NULL,
        guild_id TEXT,
        user_id TEXT NOT NULL,
        persona_name TEXT,
        content TEXT NOT NULL,
        raw_content TEXT NOT NULL,
        is_assistant BOOLEAN NOT NULL,
        parent_message_id INTEGER,
        emotion TEXT,
        FOREIGN KEY (parent_message_id) REFERENCES messages(id)
    )
    ''')
    db.commit()
    
    # Create the cog with the in-memory database
    cog = ContextCog(bot, db_path=':memory:')
    cog._db = db  # Keep the connection alive
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
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            user_id=user_id,
            content=chunk,
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
            message_id=message1_id,
            channel_id=channel_id,
            guild_id=guild_id,
            user_id=user_id,
            content=chunk,
            is_assistant=True
        )
    
    # Process second message chunks
    for chunk in chunks2:
        await context_cog.add_message_to_context(
            message_id=message2_id,
            channel_id=channel_id,
            guild_id=guild_id,
            user_id=user_id,
            content=chunk,
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
        message_id="1",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="Hello bot",
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
            message_id="2",
            channel_id=channel_id,
            guild_id=guild_id,
            user_id=user_id,
            content=chunk,
            is_assistant=True
        )
    
    # Another user message
    await context_cog.add_message_to_context(
        message_id="3",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="How are you?",
        is_assistant=False
    )
    
    # Verify message sequence
    messages = await context_cog.get_context_messages(channel_id)
    assert len(messages) == 3
    assert messages[0]['content'].endswith("Hello bot")  # User message includes username prefix
    assert messages[1]['content'] == "Hi there user"
    assert messages[2]['content'].endswith("How are you?")  # User message includes username prefix

@pytest.mark.asyncio
async def test_message_alternation_for_infermatic_model(context_cog):
    channel_id = "123"
    guild_id = "789"
    user_id = "101112"
    
    # Add three consecutive user messages
    await context_cog.add_message_to_context(
        message_id="1",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="First user message",
        is_assistant=False
    )
    
    await context_cog.add_message_to_context(
        message_id="2",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="Second user message",
        is_assistant=False
    )
    
    await context_cog.add_message_to_context(
        message_id="3",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="Third user message",
        is_assistant=False
    )
    
    # Get messages with infermatic model ID
    messages = await context_cog.get_context_messages(
        channel_id=channel_id,
        model_id="openpipe:infermatic/test-model"
    )
    
    # Verify placeholder assistant messages were inserted
    assert len(messages) == 5  # 3 user messages + 2 placeholder assistant messages
    assert messages[0]['content'].endswith("First user message")
    assert messages[1]['content'] == "[No response]"  # Placeholder assistant message
    assert messages[2]['content'].endswith("Second user message")
    assert messages[3]['content'] == "[No response]"  # Placeholder assistant message
    assert messages[4]['content'].endswith("Third user message")
    
    # Verify all messages alternate between user and assistant
    for i in range(len(messages)):
        if i % 2 == 0:
            assert messages[i]['is_assistant'] is False  # User messages
        else:
            assert messages[i]['is_assistant'] is True   # Assistant messages

@pytest.mark.asyncio
async def test_no_message_alternation_for_non_infermatic_model(context_cog):
    channel_id = "123"
    guild_id = "789"
    user_id = "101112"
    
    # Add three consecutive user messages
    await context_cog.add_message_to_context(
        message_id="1",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="First user message",
        is_assistant=False
    )
    
    await context_cog.add_message_to_context(
        message_id="2",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="Second user message",
        is_assistant=False
    )
    
    await context_cog.add_message_to_context(
        message_id="3",
        channel_id=channel_id,
        guild_id=guild_id,
        user_id=user_id,
        content="Third user message",
        is_assistant=False
    )
    
    # Get messages with non-infermatic model ID
    messages = await context_cog.get_context_messages(
        channel_id=channel_id,
        model_id="gpt-4"
    )
    
    # Verify no placeholder assistant messages were inserted
    assert len(messages) == 3  # Just the original messages
    assert messages[0]['content'].endswith("First user message")
    assert messages[1]['content'].endswith("Second user message")
    assert messages[2]['content'].endswith("Third user message")
    
    # Verify all messages are user messages
    for msg in messages:
        assert msg['is_assistant'] is False
