import discord
from discord.ext import commands
from config import CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW, MAX_CONTEXT_WINDOW, OPENPIPE_API_KEY, OPENPIPE_API_URL
import sqlite3
import json
import logging
from datetime import datetime, timedelta
import asyncio
from typing import List, Dict, Optional
import textwrap
from openai import OpenAI

class ContextCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'databases/interaction_logs.db'
        self._setup_database()
        self.summary_chunk_hours = 24  # Summarize every 24 hours of chat
        self.last_summary_check = {}  # Track last summary generation per channel
        self.openai_client = OpenAI(
            base_url=OPENPIPE_API_URL,
            api_key=OPENPIPE_API_KEY
        )
        # Track last message per role to prevent duplicates
        self.last_messages = {}  # Format: {channel_id: {'user': msg, 'assistant': msg}}
        # Track current message being built from stream
        self.current_stream = {}  # Format: {channel_id: {'content': str, 'message_id': str}}

    def _setup_database(self):
        """Initialize the SQLite database for interaction logs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Read and execute schema.sql
                with open('databases/schema.sql', 'r') as f:
                    schema = f.read()
                    cursor.executescript(schema)
                
                conn.commit()
                logging.info("Database setup completed successfully")
        except Exception as e:
            logging.error(f"Failed to set up database: {str(e)}")

    def _save_context_windows(self):
        """Save context window settings to file"""
        try:
            with open('context_windows.json', 'w') as f:
                json.dump(CONTEXT_WINDOWS, f)
            logging.info("Saved context window settings")
        except Exception as e:
            logging.error(f"Error saving context settings: {str(e)}")

    @commands.hybrid_command(name='getcontext', with_app_command=True)
    async def get_context_command(self, ctx):
        """View current context window size. Use /getcontext or !getcontext"""
        try:
            channel_id = str(ctx.channel.id)
            size = CONTEXT_WINDOWS.get(channel_id, DEFAULT_CONTEXT_WINDOW)
            await ctx.send(f"Current context window size: {size} messages")
        except Exception as e:
            logging.error(f"[Context] Error getting context size: {str(e)}")
            await ctx.send("❌ Error getting context window size")

    @commands.hybrid_command(name='setcontext', with_app_command=True)
    @commands.has_permissions(manage_messages=True)
    @discord.app_commands.describe(size="Number of messages to keep in context")
    async def set_context_command(self, ctx, size: int):
        """Set the context window size. Use /setcontext <size> or !setcontext <size>"""
        try:
            if size < 1:
                await ctx.send("❌ Context window size must be at least 1")
                return
            if size > MAX_CONTEXT_WINDOW:
                await ctx.send(f"❌ Context window size cannot exceed {MAX_CONTEXT_WINDOW}")
                return

            channel_id = str(ctx.channel.id)
            CONTEXT_WINDOWS[channel_id] = size
            self._save_context_windows()
            await ctx.send(f"✅ Context window size set to {size} messages")
        except Exception as e:
            logging.error(f"[Context] Error setting context size: {str(e)}")
            await ctx.send("❌ Error setting context window size")

    @commands.hybrid_command(name='resetcontext', with_app_command=True)
    @commands.has_permissions(manage_messages=True)
    async def reset_context_command(self, ctx):
        """Reset context window size to default. Use /resetcontext or !resetcontext"""
        try:
            channel_id = str(ctx.channel.id)
            if channel_id in CONTEXT_WINDOWS:
                del CONTEXT_WINDOWS[channel_id]
                self._save_context_windows()
            await ctx.send(f"✅ Context window size reset to default ({DEFAULT_CONTEXT_WINDOW} messages)")
        except Exception as e:
            logging.error(f"[Context] Error resetting context size: {str(e)}")
            await ctx.send("❌ Error resetting context window size")

    @commands.hybrid_command(name='clearcontext', with_app_command=True)
    @commands.has_permissions(manage_messages=True)
    @discord.app_commands.describe(hours="Number of hours of history to clear (optional)")
    async def clear_context_command(self, ctx, hours: int = None):
        """Clear conversation history. Use /clearcontext [hours] or !clearcontext [hours]"""
        try:
            channel_id = str(ctx.channel.id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if hours:
                    # Clear messages older than specified hours
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                    cursor.execute('''
                        DELETE FROM messages 
                        WHERE channel_id = ? AND timestamp < ?
                    ''', (channel_id, cutoff_time))
                    await ctx.send(f"✅ Cleared messages older than {hours} hours from context")
                else:
                    # Clear all messages
                    cursor.execute('DELETE FROM messages WHERE channel_id = ?', (channel_id,))
                    await ctx.send("✅ Cleared all messages from context")
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"[Context] Error clearing context: {str(e)}")
            await ctx.send("❌ Error clearing context")

    async def get_context_messages(self, channel_id: str, limit: int = None, exclude_message_id: str = None) -> List[Dict]:
        """Get previous messages from the context database for all users and cogs in the channel"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Always get 50 messages for API context
                window_size = 50
                if limit is not None:
                    window_size = min(window_size, limit)
                
                # Query to get messages from all users and cogs in chronological order
                query = '''
                SELECT 
                    m.discord_message_id,
                    m.user_id,
                    m.content,
                    m.is_assistant,
                    m.persona_name,
                    m.emotion,
                    m.timestamp
                FROM messages m
                WHERE m.channel_id = ?
                AND (? IS NULL OR m.discord_message_id != ?)
                AND m.content IS NOT NULL
                AND m.content != ''
                ORDER BY m.timestamp DESC
                LIMIT ?
                '''
                
                cursor.execute(query, (
                    channel_id,
                    exclude_message_id,
                    exclude_message_id,
                    window_size
                ))
                
                messages = []
                seen_contents = set()  # Track seen message contents
                
                for row in cursor.fetchall():
                    content = row[2]
                    
                    # Skip empty or whitespace-only content
                    if not content or content.isspace():
                        continue
                        
                    # Skip if we've seen this exact content before
                    if content in seen_contents:
                        continue
                        
                    # Add the content to seen_contents to skip exact duplicates
                    seen_contents.add(content)
                    
                    messages.append({
                        'id': row[0],  # discord_message_id
                        'user_id': row[1],
                        'content': content,
                        'is_assistant': bool(row[3]),
                        'persona_name': row[4],
                        'emotion': row[5],
                        'timestamp': row[6]
                    })
                
                # Reverse to maintain chronological order
                messages.reverse()
                return messages
                
        except Exception as e:
            logging.error(f"Failed to get context messages: {str(e)}")
            return []

    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        # Simple length-based comparison for performance
        if abs(len(str1) - len(str2)) / max(len(str1), len(str2)) > 0.3:
            return 0.0
        
        # Convert to sets of words for comparison
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        
        # Calculate Jaccard similarity
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0

    async def add_message_to_context(self, message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name=None, emotion=None):
        """Add a message to the interaction logs"""
        try:
            # Skip empty or whitespace-only content
            if not content or content.isspace():
                return

            # For assistant messages, accumulate content if it's part of a stream
            if is_assistant:
                if channel_id not in self.current_stream:
                    self.current_stream[channel_id] = {'content': content, 'message_id': message_id}
                else:
                    # If this is a new message ID, store the previous one and start fresh
                    if message_id != self.current_stream[channel_id]['message_id']:
                        # Store the completed message
                        await self._store_message(
                            self.current_stream[channel_id]['message_id'],
                            channel_id,
                            guild_id,
                            user_id,
                            self.current_stream[channel_id]['content'],
                            is_assistant,
                            persona_name,
                            emotion
                        )
                        # Start new message
                        self.current_stream[channel_id] = {'content': content, 'message_id': message_id}
                    else:
                        # Append to current message
                        self.current_stream[channel_id]['content'] += content
                        # Store the updated message
                        await self._store_message(
                            message_id,
                            channel_id,
                            guild_id,
                            user_id,
                            self.current_stream[channel_id]['content'],
                            is_assistant,
                            persona_name,
                            emotion
                        )
                return

            # For user messages, store directly
            await self._store_message(message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name, emotion)

        except Exception as e:
            logging.error(f"Failed to add message to context: {str(e)}")

    async def _store_message(self, message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name=None, emotion=None):
        """Store a message in the database"""
        try:
            # Check for duplicate content
            if not is_assistant:  # Only check duplicates for user messages
                last_msg = self.last_messages.get(channel_id, {}).get('user')
                if last_msg and last_msg['content'] == content:
                    logging.debug(f"Skipping duplicate message content in channel {channel_id}")
                    return

            # Get username for the message
            if is_assistant:
                # For bot messages, content already has [ModelName] prefix
                prefixed_content = content
            else:
                # For user messages, get the username
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    username = user.display_name
                    prefixed_content = f"{username}: {content}"
                except:
                    # If we can't get the username, just use the content as-is
                    prefixed_content = content

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if this message already exists
                cursor.execute('''
                SELECT content FROM messages WHERE discord_message_id = ?
                ''', (str(message_id),))
                
                existing = cursor.fetchone()
                if existing:
                    # For assistant messages, update the content to include new chunks
                    if is_assistant:
                        cursor.execute('''
                        UPDATE messages 
                        SET content = ?, 
                            emotion = COALESCE(?, emotion)
                        WHERE discord_message_id = ?
                        ''', (prefixed_content, emotion, str(message_id)))
                    else:
                        logging.debug(f"Message {message_id} already exists in context")
                        return
                else:
                    cursor.execute('''
                    INSERT INTO messages 
                    (discord_message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name, emotion, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(message_id), 
                        str(channel_id), 
                        str(guild_id) if guild_id else None, 
                        str(user_id), 
                        prefixed_content,  # Store the prefixed content
                        is_assistant, 
                        persona_name, 
                        emotion, 
                        datetime.now().isoformat()
                    ))
                
                conn.commit()

            # Update last message tracking
            if channel_id not in self.last_messages:
                self.last_messages[channel_id] = {}
            self.last_messages[channel_id]['assistant' if is_assistant else 'user'] = {
                'content': prefixed_content,
                'timestamp': datetime.now()
            }

            logging.debug(f"Added message to context: {message_id} in channel {channel_id}")
        except Exception as e:
            logging.error(f"Failed to store message in context: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages and add them to context"""
        try:
            # Skip command messages
            if message.content.startswith('!') or message.content.startswith('/'):
                return

            # Add message to context with username prefix
            guild_id = str(message.guild.id) if message.guild else None
            await self.add_message_to_context(
                message.id,
                str(message.channel.id),
                guild_id,
                str(message.author.id),
                message.content,  # Original content - username prefix added in add_message_to_context
                False,  # is_assistant
                None,   # persona_name
                None    # emotion
            )
        except Exception as e:
            logging.error(f"Error in on_message: {e}")

    async def cog_load(self):
        """Called when the cog is loaded. Sync slash commands."""
        try:
            await self.bot.tree.sync()
            logging.info("[Context] Slash commands synced successfully")
        except Exception as e:
            logging.error(f"[Context] Failed to sync slash commands: {e}")

async def setup(bot):
    await bot.add_cog(ContextCog(bot))
