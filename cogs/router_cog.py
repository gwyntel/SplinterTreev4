import discord
from discord.ext import commands
import asyncio
import logging
import aiosqlite
import json
from config import OPENROUTER_API_KEY
import aiohttp

class RouterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'databases/user_settings.db'
        self.session = None  # Will be initialized in cog_load

    async def cog_load(self):
        """Called when the cog is loaded."""
        self.session = aiohttp.ClientSession()
        await self._setup_database()
        logging.info("RouterCog has been loaded and initialized.")

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        if self.session:
            await self.session.close()
            logging.info("Closed aiohttp session in RouterCog.")

    async def _setup_database(self):
        """Initialize the SQLite database for user settings."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    store_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                await db.commit()
                logging.info("User settings database setup completed successfully.")
        except Exception as e:
            logging.error(f"Failed to set up user settings database: {str(e)}")

    async def get_store_setting(self, user_id: int) -> bool:
        """Get store setting from database."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT store_enabled FROM user_settings WHERE user_id = ?',
                (str(user_id),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return bool(row[0])
                else:
                    # Default to False if not set
                    return False

    async def set_store_setting(self, user_id: int, enabled: bool):
        """Set store setting in database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO user_settings (user_id, store_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    store_enabled = excluded.store_enabled,
                    updated_at = CURRENT_TIMESTAMP
            ''', (str(user_id), enabled))
            await db.commit()

    async def toggle_store(self, ctx, option: str):
        """Toggle the store setting for the user."""
        try:
            if isinstance(ctx, str):
                # Handle direct function call from tests
                option = ctx
                ctx = self._ctx
            
            user_id = ctx.author.id
            
            if option.lower() == 'on':
                await self.set_store_setting(user_id, True)
                await ctx.send("Store setting enabled for you.")
            elif option.lower() == 'off':
                await self.set_store_setting(user_id, False)
                await ctx.send("Store setting disabled for you.")
            else:
                await ctx.send("Invalid option. Use '!store on' or '!store off'.")
        except Exception as e:
            logging.error(f"[Router] Error toggling store setting: {str(e)}")
            await ctx.send("❌ Error updating store setting. Please try again later.")

    @commands.command(name='store')
    async def store_command(self, ctx, option: str = None):
        """Command handler for store command."""
        self._ctx = ctx  # Store context for toggle_store
        if option is None:
            # Display current setting
            is_enabled = await self.get_store_setting(ctx.author.id)
            status = "enabled" if is_enabled else "disabled"
            await ctx.send(f"Your store setting is currently {status}. Use '!store on' or '!store off' to change it.")
        else:
            await self.toggle_store(ctx, option)

    async def is_store_enabled(self, user_id: int) -> bool:
        """Check if the store setting is enabled for a user."""
        try:
            return await self.get_store_setting(user_id)
        except Exception as e:
            logging.error(f"[Router] Error checking store setting: {str(e)}")
            return False

    async def route_message(self, message: discord.Message):
        """Route the message to the appropriate model."""
        try:
            response = await self.session.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'HTTP-Referer': 'https://github.com/gwyntel/SplinterTreev4',
                    'X-Title': 'SplinterTree by GwynTel'
                },
                json={
                    'model': 'mistralai/mixtral-8x7b-instruct',
                    'messages': [
                        {'role': 'user', 'content': message.content}
                    ]
                }
            )
            
            # Get response data
            data = await response.json()
            
            # Extract content from response
            if data and 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                await message.channel.send(content)
            else:
                await message.channel.send("❌ Failed to process message. Please try again later.")
                
        except Exception as e:
            logging.error(f"[Router] Error routing message: {str(e)}")
            await message.channel.send("❌ An error occurred while processing your message.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip if message is from the bot itself
        if message.author == self.bot.user:
            return

        # Process the message routing
        await self.route_message(message)

    async def cog_check(self, ctx):
        """Ensure that commands are only used in guilds, except for the 'store' command."""
        if ctx.command.name == 'store':
            return True  # Allow 'store' command in DMs
        return ctx.guild is not None

async def setup(bot):
    await bot.add_cog(RouterCog(bot))
