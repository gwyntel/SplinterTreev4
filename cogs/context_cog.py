import discord
from discord.ext import commands
from config import CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW, MAX_CONTEXT_WINDOW
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

def is_bot_tender():
    async def predicate(ctx):
        if not ctx.guild:
            return False
        return discord.utils.get(ctx.author.roles, name="Bot Tender") is not None
    return commands.check(predicate)

class ContextCog(commands.Cog):
    def __init__(self, bot, db_path=None):
        self.bot = bot
        self.db_path = db_path or 'databases/interaction_logs.db'
        self._db = None
        self._setup_database()
        self.context_windows = CONTEXT_WINDOWS
        self.default_context_window = DEFAULT_CONTEXT_WINDOW
        self.max_context_window = MAX_CONTEXT_WINDOW
        self.message_ids = set()  # Track added message IDs

    def _setup_database(self):
        """Setup the database synchronously."""
        try:
            self._db = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self._db.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_message_id TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                channel_id TEXT NOT NULL,
                guild_id TEXT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                is_assistant BOOLEAN NOT NULL
            )
            ''')
            self._db.commit()
            logging.info("Database setup completed successfully.")
        except Exception as e:
            logging.error(f"Failed to set up database: {str(e)}")

    async def get_context_messages(self, channel_id: str, limit: int = 50, exclude_message_id: Optional[str] = None) -> List[Dict]:
        """Retrieve the last N messages for context."""
        try:
            cursor = self._db.cursor()
            query = '''
            SELECT discord_message_id, user_id, content, raw_content, is_assistant, timestamp
            FROM messages
            WHERE channel_id = ?
            AND (? IS NULL OR discord_message_id != ?)
            ORDER BY timestamp DESC
            LIMIT ?
            '''
            cursor.execute(query, (channel_id, exclude_message_id, exclude_message_id, limit))
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                if row[0] not in self.message_ids:  # Skip already added messages
                    messages.append({
                        'id': row[0],
                        'user_id': row[1],
                        'content': row[2],
                        'raw_content': row[3],
                        'is_assistant': bool(row[4]),
                        'timestamp': row[5]
                    })
            return messages[::-1]  # Reverse to chronological order
        except Exception as e:
            logging.error(f"Failed to retrieve context messages: {str(e)}")
            return []

    async def add_message_to_context(self, message_id: str, channel_id: str, guild_id: str, user_id: str, content: str, is_assistant: bool):
        """Add a message to the context."""
        try:
            if message_id in self.message_ids:
                return  # Skip if already added
            self.message_ids.add(message_id)
            cursor = self._db.cursor()
            cursor.execute('''
            INSERT INTO messages (discord_message_id, channel_id, guild_id, user_id, content, raw_content, is_assistant)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message_id, channel_id, guild_id, user_id, content, content, is_assistant))  # Use content for raw_content
            self._db.commit()
        except Exception as e:
            logging.error(f"Failed to add message to context: {str(e)}")

    def _save_context_windows(self):
        """Save context window settings to a file."""
        try:
            with open('context_windows.json', 'w') as f:
                json.dump(self.context_windows, f, indent=2)
            logging.info("Saved context window settings.")
        except Exception as e:
            logging.error(f"Error saving context settings: {str(e)}")

    @commands.hybrid_command(name='getcontext', with_app_command=True)
    async def get_context_command(self, ctx):
        """View current context window size."""
        try:
            channel_id = str(ctx.channel.id)
            size = self.context_windows.get(channel_id, self.default_context_window)
            await ctx.send(f"Current context window size: {size} messages")
        except Exception as e:
            logging.error(f"Error getting context size: {str(e)}")
            await ctx.send("❌ Error getting context window size")

    @commands.hybrid_command(name='setcontext', with_app_command=True)
    @is_bot_tender()
    async def set_context_command(self, ctx, size: int):
        """Set the context window size."""
        try:
            if size < 1:
                await ctx.send("❌ Context window size must be at least 1")
                return
            if size > self.max_context_window:
                await ctx.send(f"❌ Context window size cannot exceed {self.max_context_window}")
                return

            channel_id = str(ctx.channel.id)
            self.context_windows[channel_id] = size
            self._save_context_windows()
            await ctx.send(f"✅ Context window size set to {size} messages")
        except Exception as e:
            logging.error(f"Error setting context size: {str(e)}")
            await ctx.send("❌ Error setting context window size")

    @commands.hybrid_command(name='resetcontext', with_app_command=True)
    @is_bot_tender()
    async def reset_context_command(self, ctx):
        """Reset context window size to default."""
        try:
            channel_id = str(ctx.channel.id)
            if channel_id in self.context_windows:
                del self.context_windows[channel_id]
                self._save_context_windows()
            await ctx.send(f"✅ Context window size reset to default ({self.default_context_window} messages)")
        except Exception as e:
            logging.error(f"Error resetting context size: {str(e)}")
            await ctx.send("❌ Error resetting context window size")

    @commands.hybrid_command(name='clearcontext', with_app_command=True)
    @is_bot_tender()
    async def clear_context_command(self, ctx, hours: int = None):
        """Clear conversation history."""
        try:
            channel_id = str(ctx.channel.id)
            cursor = self._db.cursor()
            if hours:
                cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                cursor.execute('DELETE FROM messages WHERE channel_id = ? AND timestamp < ?', (channel_id, cutoff_time))
                await ctx.send(f"✅ Cleared messages older than {hours} hours from context")
            else:
                cursor.execute('DELETE FROM messages WHERE channel_id = ?', (channel_id,))
                await ctx.send("✅ Cleared all messages from context")
            self._db.commit()
        except Exception as e:
            logging.error(f"Error clearing context: {str(e)}")
            await ctx.send("❌ Error clearing context")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for new messages and add them to the context."""
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
                False
            )
        except Exception as e:
            logging.error(f"Error in on_message: {e}")

async def setup(bot):
    await bot.add_cog(ContextCog(bot))
