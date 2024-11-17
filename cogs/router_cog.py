import discord
from discord.ext import commands
import asyncio
import logging
import aiosqlite
import json
from datetime import datetime, timezone
from shared.api import api

class RouterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'databases/user_settings.db'
        self.start_time = datetime.now(timezone.utc)
        self.activated_channels = self._load_activated_channels()
        # Load the system prompt
        self.router_system_prompt = self._load_router_system_prompt()

    def _load_router_system_prompt(self):
        """Load the router system prompt from a file or return the default."""
        try:
            with open('router_system_prompt.txt', 'r') as f:
                prompt = f.read()
            return prompt
        except FileNotFoundError:
            logging.error("[Router] System prompt file not found.")
            return ""

    def _load_activated_channels(self) -> dict:
        """Load activated channels from file"""
        try:
            with open('activated_channels.json', 'r') as f:
                channels = json.load(f)
                logging.info(f"[Router] Loaded activated channels: {channels}")
                return channels
        except FileNotFoundError:
            logging.info("[Router] No activated channels file found, creating new one")
            self._save_activated_channels({})
            return {}
        except Exception as e:
            logging.error(f"[Router] Error loading activated channels: {e}")
            return {}

    def _save_activated_channels(self, channels: dict):
        """Save activated channels to file"""
        try:
            with open('activated_channels.json', 'w') as f:
                json.dump(channels, f)
            logging.info(f"[Router] Saved activated channels: {channels}")
        except Exception as e:
            logging.error(f"[Router] Error saving activated channels: {e}")

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

    @commands.command(name='store')
    async def store_command(self, ctx, option: str = None):
        """Toggle message storage for the user. Usage: !store [on|off]"""
        try:
            if option is None:
                # Display current setting
                is_enabled = await self.get_store_setting(ctx.author.id)
                status = "enabled" if is_enabled else "disabled"
                await ctx.send(f"Your store setting is currently {status}. Use '!store on' or '!store off' to change it.")
                return

            option = option.lower()
            if option not in ['on', 'off']:
                await ctx.send("Invalid option. Use '!store on' or '!store off'.")
                return

            enabled = option == 'on'
            await self.set_store_setting(ctx.author.id, enabled)
            await ctx.send(f"Store setting {'enabled' if enabled else 'disabled'} for you.")

        except Exception as e:
            logging.error(f"[Router] Error in store command: {str(e)}")
            await ctx.send("❌ Error updating store setting. Please try again later.")

    @commands.command(name='activate')
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def activate_command(self, ctx):
        """Activate the bot in the current channel. Admin only."""
        try:
            if not ctx.guild:
                await ctx.send("❌ This command can only be used in a server.")
                return

            guild_id = str(ctx.guild.id)
            channel_id = str(ctx.channel.id)

            if guild_id not in self.activated_channels:
                self.activated_channels[guild_id] = {}

            if channel_id in self.activated_channels[guild_id]:
                await ctx.send("Bot is already activated in this channel.")
                return

            self.activated_channels[guild_id][channel_id] = True
            self._save_activated_channels(self.activated_channels)

            # Update HelpCog's activated channels
            help_cog = self.bot.get_cog('Help')
            if help_cog:
                help_cog.activated_channels = self.activated_channels

            await ctx.send("✅ Bot activated in this channel.")
            logging.info(f"[Router] Activated channel {channel_id} in guild {guild_id}")

        except Exception as e:
            logging.error(f"[Router] Error in activate command: {str(e)}")
            await ctx.send("❌ Error activating bot. Please try again later.")

    @commands.command(name='deactivate')
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def deactivate_command(self, ctx):
        """Deactivate the bot in the current channel. Admin only."""
        try:
            if not ctx.guild:
                await ctx.send("❌ This command can only be used in a server.")
                return

            guild_id = str(ctx.guild.id)
            channel_id = str(ctx.channel.id)

            if guild_id not in self.activated_channels or channel_id not in self.activated_channels[guild_id]:
                await ctx.send("Bot is not activated in this channel.")
                return

            del self.activated_channels[guild_id][channel_id]
            if not self.activated_channels[guild_id]:
                del self.activated_channels[guild_id]
            self._save_activated_channels(self.activated_channels)

            # Update HelpCog's activated channels
            help_cog = self.bot.get_cog('Help')
            if help_cog:
                help_cog.activated_channels = self.activated_channels

            await ctx.send("✅ Bot deactivated in this channel.")
            logging.info(f"[Router] Deactivated channel {channel_id} in guild {guild_id}")

        except Exception as e:
            logging.error(f"[Router] Error in deactivate command: {str(e)}")
            await ctx.send("❌ Error deactivating bot. Please try again later.")

    @commands.command(name='uptime')
    async def uptime_command(self, ctx):
        """Show how long the bot has been running."""
        try:
            current_time = datetime.now(timezone.utc)
            delta = current_time - self.start_time

            # Calculate time components
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60

            # Build uptime string
            uptime_parts = []
            if days > 0:
                uptime_parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                uptime_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                uptime_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds > 0 or not uptime_parts:
                uptime_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

            uptime_str = ", ".join(uptime_parts)
            await ctx.send(f"Bot has been running for {uptime_str}.")

        except Exception as e:
            logging.error(f"[Router] Error in uptime command: {str(e)}")
            await ctx.send("❌ Error getting uptime. Please try again later.")

    async def route_message(self, message: discord.Message):
        """Route the message to the appropriate cog based on the model's decision."""
        try:
            # Check if channel is activated
            guild_id = str(message.guild.id) if message.guild else None
            channel_id = str(message.channel.id)

            if not guild_id or guild_id not in self.activated_channels or channel_id not in self.activated_channels[guild_id]:
                return  # Channel not activated

            # Prepare the system prompt
            system_prompt = self.router_system_prompt

            # Format the system prompt with the user message (and context if available)
            formatted_prompt = system_prompt.replace("{user_message}", message.content).replace("{context}", "")  # Add context if available

            # Prepare messages for the model
            messages = [
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": message.content}
            ]

            # Call the routing model
            response = await api.call_openpipe(
                messages=messages,
                model='meta-llama/llama-3.2-3b-instruct',
                user_id=str(message.author.id),
                guild_id=guild_id
            )

            # Extract the routing decision
            if response and 'choices' in response and len(response['choices']) > 0:
                routing_response = response['choices'][0]['message']['content']
                # Clean up the response to get the cog name
                cog_name = routing_response.strip()

                # Attempt to get the cog
                cog = self.bot.get_cog(cog_name + "Cog")
                if cog and hasattr(cog, 'handle_message'):
                    # Forward the message to the cog
                    await cog.handle_message(message)
                else:
                    await message.channel.send("❌ Unable to route message to the appropriate module.")
                    logging.error(f"[Router] Cog '{cog_name}Cog' not found or 'handle_message' not implemented.")
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
