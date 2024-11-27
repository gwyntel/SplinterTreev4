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
        self.summary_chunk_hours = 24
        self.last_summary_check = {}
        self.openai_client = OpenAI(
            base_url=OPENPIPE_API_URL,
            api_key=OPENPIPE_API_KEY
        )
        self.last_messages = {}
        self.current_stream = {}
        self.message_cache = {}  # Add message cache
        self.cache_timeout = 300  # 5 minutes cache timeout

    def _setup_database(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                with open('databases/schema.sql', 'r') as f:
                    schema = f.read()
                    cursor.executescript(schema)
                conn.commit()
                logging.info("Database setup completed successfully")
        except Exception as e:
            logging.error(f"Failed to set up database: {str(e)}")

    def _save_context_windows(self):
        try:
            with open('context_windows.json', 'w') as f:
                json.dump({
                    "DEFAULT_CONTEXT_WINDOW": DEFAULT_CONTEXT_WINDOW,
                    "CONTEXT_WINDOWS": CONTEXT_WINDOWS
                }, f, indent=2)
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
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                    cursor.execute('''
                        DELETE FROM messages 
                        WHERE channel_id = ? AND timestamp < ?
                    ''', (channel_id, cutoff_time))
                    await ctx.send(f"✅ Cleared messages older than {hours} hours from context")
                else:
                    cursor.execute('DELETE FROM messages WHERE channel_id = ?', (channel_id,))
                    await ctx.send("✅ Cleared all messages from context")
                
                conn.commit()
                
                # Clear cache for this channel
                cache_keys_to_remove = [k for k in self.message_cache if k.startswith(f"{channel_id}:")]
                for key in cache_keys_to_remove:
                    self.message_cache.pop(key, None)
                
        except Exception as e:
            logging.error(f"[Context] Error clearing context: {str(e)}")
            await ctx.send("❌ Error clearing context")

    async def get_context_messages(self, channel_id: str, limit: int = None, exclude_message_id: str = None, model_id: str = None) -> List[Dict]:
        cache_key = f"{channel_id}:{limit}:{exclude_message_id}"
        
        # Check cache first
        if cache_key in self.message_cache:
            cache_entry = self.message_cache[cache_key]
            if datetime.now().timestamp() - cache_entry['timestamp'] < self.cache_timeout:
                messages = cache_entry['messages']
                # Apply message alternation if needed
                if model_id and "infermatic" in model_id.lower():
                    messages = self._ensure_message_alternation(messages)
                return messages
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                window_size = min(50, limit) if limit is not None else 50
                
                query = '''
                SELECT DISTINCT
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
                seen_contents = set()
                
                for row in cursor.fetchall():
                    content = row[2]
                    if not content or content.isspace() or content in seen_contents:
                        continue
                    seen_contents.add(content)
                    
                    messages.append({
                        'id': row[0],
                        'user_id': row[1],
                        'content': content,
                        'is_assistant': bool(row[3]),
                        'persona_name': row[4],
                        'emotion': row[5],
                        'timestamp': row[6]
                    })
                
                messages.reverse()
                
                # Apply message alternation if needed
                if model_id and "infermatic" in model_id.lower():
                    messages = self._ensure_message_alternation(messages)
                
                # Cache the results
                self.message_cache[cache_key] = {
                    'messages': messages,
                    'timestamp': datetime.now().timestamp()
                }
                
                return messages
                
        except Exception as e:
            logging.error(f"Failed to get context messages: {str(e)}")
            return []

    def _ensure_message_alternation(self, messages: List[Dict]) -> List[Dict]:
        """Ensure messages alternate between user and assistant by inserting blank assistant messages where needed."""
        if not messages:
            return messages

        result = []
        last_was_user = None

        for msg in messages:
            is_user = not msg['is_assistant']
            
            # If this is a user message and the last message was also from a user,
            # insert a blank assistant message
            if is_user and last_was_user:
                result.append({
                    'id': f"blank_{len(result)}",
                    'user_id': None,
                    'content': "",  # Blank message
                    'is_assistant': True,
                    'persona_name': None,
                    'emotion': None,
                    'timestamp': msg['timestamp']  # Use same timestamp as the user message
                })
            
            result.append(msg)
            last_was_user = is_user

        return result

    async def add_message_to_context(self, message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name=None, emotion=None):
        try:
            if not content or content.isspace():
                return

            if is_assistant:
                if channel_id not in self.current_stream:
                    self.current_stream[channel_id] = {'content': '', 'message_id': message_id}
                
                if message_id != self.current_stream[channel_id]['message_id']:
                    # Store the previous complete message before starting a new one
                    if self.current_stream[channel_id]['content']:
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
                    # Start a new message stream
                    self.current_stream[channel_id] = {'content': content, 'message_id': message_id}
                else:
                    # Append to existing message stream
                    self.current_stream[channel_id]['content'] = content
                    # Store the updated complete message
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

            await self._store_message(message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name, emotion)

        except Exception as e:
            logging.error(f"Failed to add message to context: {str(e)}")

    async def _store_message(self, message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name=None, emotion=None):
        try:
            if not is_assistant:
                last_msg = self.last_messages.get(channel_id, {}).get('user')
                if last_msg and last_msg['content'] == content:
                    return

            if is_assistant:
                prefixed_content = content
            else:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    username = user.display_name
                    prefixed_content = f"{username}: {content}"
                except:
                    prefixed_content = content

            async with asyncio.Lock():
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO messages 
                    (discord_message_id, channel_id, guild_id, user_id, content, is_assistant, persona_name, emotion, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(message_id), 
                        str(channel_id), 
                        str(guild_id) if guild_id else None, 
                        str(user_id), 
                        prefixed_content,
                        is_assistant, 
                        persona_name, 
                        emotion, 
                        datetime.now().isoformat()
                    ))
                    
                    conn.commit()

            if channel_id not in self.last_messages:
                self.last_messages[channel_id] = {}
            self.last_messages[channel_id]['assistant' if is_assistant else 'user'] = {
                'content': prefixed_content,
                'timestamp': datetime.now()
            }

            # Clear relevant cache entries
            cache_keys_to_remove = [k for k in self.message_cache if k.startswith(f"{channel_id}:")]
            for key in cache_keys_to_remove:
                self.message_cache.pop(key, None)

        except Exception as e:
            logging.error(f"Failed to store message in context: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.startswith('!') or message.content.startswith('/'):
            return

        try:
            guild_id = str(message.guild.id) if message.guild else None
            await self.add_message_to_context(
                message.id,
                str(message.channel.id),
                guild_id,
                str(message.author.id),
                message.content,
                False,
                None,
                None
            )
        except Exception as e:
            logging.error(f"Error in on_message: {e}")

    async def cog_load(self):
        try:
            await self.bot.tree.sync()
            logging.info("[Context] Slash commands synced successfully")
        except Exception as e:
            logging.error(f"[Context] Failed to sync slash commands: {e}")

async def setup(bot):
    await bot.add_cog(ContextCog(bot))
