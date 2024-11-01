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
import backoff

class ContextCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'databases/interaction_logs.db'
        self._setup_database()
        self.summary_chunk_hours = 24  # Summarize every 24 hours of chat
        self.last_summary_check = {}  # Track last summary generation per channel
        self.summary_locks = {}  # Lock per channel for summary generation
        self.openai_client = OpenAI(
            base_url=OPENPIPE_API_URL,
            api_key=OPENPIPE_API_KEY
        )

    def _setup_database(self):
        """Ensure database and tables exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Load and execute schema if needed
                with open('databases/schema.sql', 'r') as f:
                    conn.executescript(f.read())
        except Exception as e:
            logging.error(f"Failed to setup database: {str(e)}")

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=3,
        max_time=30
    )
    async def _generate_summary(self, messages: List[Dict]) -> str:
        """Generate a summary of chat messages using OpenAI/OpenPipe"""
        if not messages:
            return "No messages to summarize."

        try:
            # Format messages for the API
            formatted_messages = []
            for msg in messages:
                speaker = "Assistant" if msg['is_assistant'] else f"User {msg['user_id']}"
                formatted_messages.append(f"{speaker}: {msg['content']}")

            conversation = "\n".join(formatted_messages)
            
            # Create system prompt for summarization
            system_prompt = """You are a helpful assistant that summarizes Discord chat conversations. Create a concise summary that:
1. Captures the main points and key interactions
2. Highlights important topics discussed
3. Notes any decisions or conclusions reached
4. Preserves context that might be relevant for future messages
5. Maintains a neutral, objective tone

Keep the summary clear and well-structured, but brief enough to serve as useful context."""

            # Make API call
            completion = self.openai_client.chat.completions.create(
                model="openpipe:moa-gpt-4o-v1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Please summarize this conversation:\n\n{conversation}"}
                ],
                store=True,
                metadata={"type": "discord_summary"}
            )

            summary = completion.choices[0].message.content
            return summary

        except Exception as e:
            logging.error(f"Failed to generate summary: {str(e)}")
            return f"Error generating summary: {str(e)}"

    async def _check_and_create_summary(self, channel_id: str):
        """Check if we need to create a new summary and create it if necessary"""
        # Get or create lock for this channel
        if channel_id not in self.summary_locks:
            self.summary_locks[channel_id] = asyncio.Lock()

        # Use lock to prevent multiple simultaneous summaries
        async with self.summary_locks[channel_id]:
            try:
                # Check if we've recently checked this channel
                now = datetime.now()
                if channel_id in self.last_summary_check:
                    time_since_check = (now - self.last_summary_check[channel_id]).total_seconds()
                    if time_since_check < 3600:  # Don't check more than once per hour
                        return
                
                self.last_summary_check[channel_id] = now

                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Get the timestamp of the last summary
                    cursor.execute("""
                        SELECT MAX(end_timestamp) FROM chat_summaries
                        WHERE channel_id = ?
                    """, (channel_id,))
                    last_summary = cursor.fetchone()[0]
                    
                    if last_summary:
                        last_summary = datetime.fromisoformat(last_summary)
                    else:
                        last_summary = datetime.now() - timedelta(hours=self.summary_chunk_hours)

                    # Get messages since last summary
                    cursor.execute("""
                        SELECT 
                            timestamp, user_id, persona_name, 
                            content, is_assistant, emotion
                        FROM messages
                        WHERE channel_id = ? AND timestamp > ?
                        ORDER BY timestamp ASC
                    """, (channel_id, last_summary.isoformat()))

                    messages = []
                    for row in cursor.fetchall():
                        messages.append({
                            'timestamp': row[0],
                            'user_id': row[1],
                            'persona_name': row[2],
                            'content': row[3],
                            'is_assistant': bool(row[4]),
                            'emotion': row[5]
                        })

                    if messages:
                        start_time = last_summary
                        end_time = datetime.fromisoformat(messages[-1]['timestamp'])
                        
                        # Only create summary if we have at least summary_chunk_hours worth of messages
                        if (end_time - start_time) >= timedelta(hours=self.summary_chunk_hours):
                            summary = await self._generate_summary(messages)
                            
                            cursor.execute("""
                                INSERT INTO chat_summaries 
                                (channel_id, start_timestamp, end_timestamp, summary)
                                VALUES (?, ?, ?, ?)
                            """, (channel_id, start_time.isoformat(), 
                                  end_time.isoformat(), summary))
                            conn.commit()
                            logging.info(f"Created new summary for channel {channel_id}")

            except Exception as e:
                logging.error(f"Failed to create summary: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Capture user messages to add to context"""
        if message.author.bot:
            return

        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id) if message.guild else None
        user_id = str(message.author.id)
        content = message.content
        is_assistant = False
        persona_name = None
        emotion = None

        await self.add_message_to_context(channel_id, guild_id, user_id, content, 
                                        is_assistant, persona_name, emotion)
        
        # Check if we need to create a new summary
        asyncio.create_task(self._check_and_create_summary(channel_id))

    async def get_context_messages(self, channel_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation context for a channel"""
        try:
            if limit is None:
                limit = CONTEXT_WINDOWS.get(channel_id, DEFAULT_CONTEXT_WINDOW)
            
            limit = min(limit, MAX_CONTEXT_WINDOW)  # Ensure we don't exceed maximum

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get relevant summaries
                cursor.execute("""
                    SELECT summary, end_timestamp
                    FROM chat_summaries
                    WHERE channel_id = ?
                    ORDER BY end_timestamp DESC
                    LIMIT 3
                """, (channel_id,))
                summaries = cursor.fetchall()

                # Get recent messages
                cursor.execute("""
                    SELECT 
                        timestamp,
                        user_id,
                        persona_name,
                        content,
                        is_assistant,
                        emotion
                    FROM messages
                    WHERE channel_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (channel_id, limit))

                messages = []
                
                # Add system message with summary if available
                if summaries:
                    latest_summary = summaries[0]
                    messages.append({
                        "role": "system",
                        "content": f"Previous conversation summary: {latest_summary['summary']}"
                    })

                # Add recent messages in chronological order
                rows = cursor.fetchall()
                for row in reversed(rows):  # Reverse to get chronological order
                    message = {
                        "role": "assistant" if row['is_assistant'] else "user",
                        "content": row['content']
                    }
                    messages.append(message)

                return messages

        except Exception as e:
            logging.error(f"Failed to get context messages: {str(e)}")
            return []

    async def add_message_to_context(self, channel_id: str, guild_id: Optional[str], 
                                   user_id: str, content: str, is_assistant: bool,
                                   persona_name: Optional[str] = None, 
                                   emotion: Optional[str] = None) -> bool:
        """Add a new message to the conversation context"""
        try:
            timestamp = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages (
                        channel_id, guild_id, user_id, persona_name, 
                        content, is_assistant, emotion, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (channel_id, guild_id, user_id, persona_name, 
                      content, is_assistant, emotion, timestamp))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Failed to add message to context: {str(e)}")
            return False

    @commands.command(name='summarize')
    @commands.has_permissions(manage_messages=True)
    async def force_summarize(self, ctx):
        """Force create a summary for the current channel"""
        channel_id = str(ctx.channel.id)
        try:
            async with ctx.typing():
                await self._check_and_create_summary(channel_id)
            await ctx.reply("✅ Created new chat summary")
        except Exception as e:
            logging.error(f"Failed to force summarize: {str(e)}")
            await ctx.reply("❌ Failed to create chat summary")

    @commands.command(name='getsummaries')
    async def get_summaries(self, ctx, hours: Optional[int] = 24):
        """Get chat summaries for this channel"""
        channel_id = str(ctx.channel.id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                
                cursor.execute("""
                    SELECT summary, start_timestamp, end_timestamp
                    FROM chat_summaries
                    WHERE channel_id = ? AND end_timestamp > ?
                    ORDER BY end_timestamp DESC
                """, (channel_id, cutoff_time))
                
                summaries = cursor.fetchall()
                
                if not summaries:
                    await ctx.reply("No summaries found for the specified time period.")
                    return

                response = "📝 Chat Summaries:\n\n"
                for summary in summaries:
                    start_time = datetime.fromisoformat(summary[1])
                    end_time = datetime.fromisoformat(summary[2])
                    response += f"From {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}:\n"
                    response += f"{summary[0]}\n\n"

                # Split response if it's too long
                if len(response) > 2000:
                    parts = textwrap.wrap(response, 2000)
                    for part in parts:
                        await ctx.reply(part)
                else:
                    await ctx.reply(response)

        except Exception as e:
            logging.error(f"Failed to get summaries: {str(e)}")
            await ctx.reply("❌ Failed to retrieve chat summaries")

    @commands.command(name='clearsummaries')
    @commands.has_permissions(manage_messages=True)
    async def clear_summaries(self, ctx, hours: Optional[int] = None):
        """Clear chat summaries for this channel"""
        channel_id = str(ctx.channel.id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if hours:
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                    cursor.execute("""
                        DELETE FROM chat_summaries
                        WHERE channel_id = ? AND end_timestamp < ?
                    """, (channel_id, cutoff_time))
                else:
                    cursor.execute("""
                        DELETE FROM chat_summaries
                        WHERE channel_id = ?
                    """, (channel_id,))
                conn.commit()

                await ctx.reply(f"🗑️ Cleared chat summaries{f' older than {hours} hours' if hours else ''}")
        except Exception as e:
            logging.error(f"Failed to clear summaries: {str(e)}")
            await ctx.reply("❌ Failed to clear chat summaries")

async def setup(bot):
    await bot.add_cog(ContextCog(bot))
