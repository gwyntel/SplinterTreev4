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

    async def send_response(self, ctx, content: str):
        """Helper method to handle sending responses for both prefix and slash commands."""
        if isinstance(ctx, discord.Interaction):
            if not ctx.response.is_done():
                await ctx.response.send_message(content)
            else:
                await ctx.followup.send(content)
        else:
            await ctx.send(content)

    @commands.hybrid_command(name='store', with_app_command=True)
    @discord.app_commands.describe(option="Turn message storage on or off")
    @discord.app_commands.choices(option=[
        discord.app_commands.Choice(name="on", value="on"),
        discord.app_commands.Choice(name="off", value="off")
    ])
    async def store_command(self, ctx, option: str = None):
        """Toggle message storage for the user. Use /store or !store [on|off]"""
        try:
            user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            if option is None:
                # Display current setting
                is_enabled = await self.get_store_setting(user_id)
                status = "enabled" if is_enabled else "disabled"
                await self.send_response(ctx, f"Your store setting is currently {status}. Use '/store on' or '/store off' to change it.")
                return

            option = option.lower()
            if option not in ['on', 'off']:
                await self.send_response(ctx, "Invalid option. Use '/store on' or '/store off'.")
                return

            enabled = option == 'on'
            await self.set_store_setting(user_id, enabled)
            await self.send_response(ctx, f"Store setting {'enabled' if enabled else 'disabled'} for you.")

        except Exception as e:
            logging.error(f"[Router] Error in store command: {str(e)}")
            await self.send_response(ctx, "❌ Error updating store setting. Please try again later.")

    @commands.hybrid_command(name='activate', with_app_command=True)
    @commands.has_permissions(administrator=True)
    async def activate_command(self, ctx):
        """Activate the bot in the current channel. Use /activate or !activate"""
        try:
            channel_id = str(ctx.channel.id)
            
            if isinstance(ctx.channel, discord.DMChannel):
                # Handle DM activation
                if 'DM' not in self.activated_channels:
                    self.activated_channels['DM'] = {}
                
                if channel_id in self.activated_channels['DM']:
                    await self.send_response(ctx, "Bot is already activated in this DM.")
                    return

                self.activated_channels['DM'][channel_id] = True
            else:
                # Handle guild channel activation
                user = ctx.author if hasattr(ctx, 'author') else ctx.user
                if not user.guild_permissions.administrator:
                    await self.send_response(ctx, "❌ You need administrator permissions to use this command in a server.")
                    return

                guild_id = str(ctx.guild.id)
                if guild_id not in self.activated_channels:
                    self.activated_channels[guild_id] = {}

                if channel_id in self.activated_channels[guild_id]:
                    await self.send_response(ctx, "Bot is already activated in this channel.")
                    return

                self.activated_channels[guild_id][channel_id] = True

            self._save_activated_channels(self.activated_channels)

            # Update HelpCog's activated channels
            help_cog = self.bot.get_cog('Help')
            if help_cog:
                help_cog.activated_channels = self.activated_channels

            await self.send_response(ctx, "✅ Bot activated in this channel.")
            logging.info(f"[Router] Activated channel {channel_id}")

        except Exception as e:
            logging.error(f"[Router] Error in activate command: {str(e)}")
            await self.send_response(ctx, "❌ Error activating bot. Please try again later.")

    @commands.hybrid_command(name='deactivate', with_app_command=True)
    @commands.has_permissions(administrator=True)
    async def deactivate_command(self, ctx):
        """Deactivate the bot in the current channel. Use /deactivate or !deactivate"""
        try:
            channel_id = str(ctx.channel.id)

            if isinstance(ctx.channel, discord.DMChannel):
                # Handle DM deactivation
                if 'DM' not in self.activated_channels or channel_id not in self.activated_channels['DM']:
                    await self.send_response(ctx, "Bot is not activated in this DM.")
                    return

                del self.activated_channels['DM'][channel_id]
                if not self.activated_channels['DM']:
                    del self.activated_channels['DM']
            else:
                # Handle guild channel deactivation
                user = ctx.author if hasattr(ctx, 'author') else ctx.user
                if not user.guild_permissions.administrator:
                    await self.send_response(ctx, "❌ You need administrator permissions to use this command in a server.")
                    return

                guild_id = str(ctx.guild.id)
                if guild_id not in self.activated_channels or channel_id not in self.activated_channels[guild_id]:
                    await self.send_response(ctx, "Bot is not activated in this channel.")
                    return

                del self.activated_channels[guild_id][channel_id]
                if not self.activated_channels[guild_id]:
                    del self.activated_channels[guild_id]

            self._save_activated_channels(self.activated_channels)

            # Update HelpCog's activated channels
            help_cog = self.bot.get_cog('Help')
            if help_cog:
                help_cog.activated_channels = self.activated_channels

            await self.send_response(ctx, "✅ Bot deactivated in this channel.")
            logging.info(f"[Router] Deactivated channel {channel_id}")

        except Exception as e:
            logging.error(f"[Router] Error in deactivate command: {str(e)}")
            await self.send_response(ctx, "❌ Error deactivating bot. Please try again later.")

    @commands.hybrid_command(name='uptime', with_app_command=True)
    async def uptime_command(self, ctx):
        """Show how long the bot has been running. Use /uptime or !uptime"""
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
            await self.send_response(ctx, f"Bot has been running for {uptime_str}.")

        except Exception as e:
            logging.error(f"[Router] Error in uptime command: {str(e)}")
            await self.send_response(ctx, "❌ Error getting uptime. Please try again later.")

    async def handle_message(self, message: discord.Message):
        """Route the message to the appropriate cog based on the model's decision."""
        try:
            channel_id = str(message.channel.id)
            is_dm = isinstance(message.channel, discord.DMChannel)

            # Check if channel is activated
            if is_dm:
                if 'DM' not in self.activated_channels or channel_id not in self.activated_channels['DM']:
                    return  # DM not activated
            else:
                guild_id = str(message.guild.id)
                if guild_id not in self.activated_channels or channel_id not in self.activated_channels[guild_id]:
                    return  # Channel not activated

            # Check if the message contains any excluded model names
            excluded_models = [
                'Gemini', 'Magnum', 'Sonar', 'Sydney', 'Goliath',
                'Pixtral', 'Mixtral', 'Claude3Haiku', 'Inferor',
                'Nemotron', 'Noromaid', 'Rplus', 'Router',
                'Llama32_11b', 'Llama32_90b', 'OpenChat', 'Dolphin',
                'Gemma', 'Ministral', 'Liquid', 'Hermes', 'Sorcerer'
            ]
            if any(model in message.content for model in excluded_models):
                logging.info(f"[Router] Message contains excluded model name. Skipping response.")
                return  # Do not respond if an excluded model name is mentioned

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
                model='mistralai/ministral-3b',
                user_id=str(message.author.id),
                guild_id=str(message.guild.id) if message.guild else None
            )

            # Log the full model response for debugging
            logging.info(f"[Router] Full model response: {response}")

            # Extract the routing decision
            if response and 'choices' in response and len(response['choices']) > 0:
                routing_response = response['choices'][0]['message']['content']
                # Clean up the response to get the cog name
                cog_name = routing_response.strip().split('\n')[0].strip()
                
                # Remove any extra text or punctuation
                cog_name = ''.join(c for c in cog_name if c.isalnum())
                
                logging.info(f"[Router] Cleaned cog name: {cog_name}")

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

    async def cog_load(self):
        """Called when the cog is loaded. Sync slash commands."""
        try:
            await self.bot.tree.sync()
            logging.info("[Router] Slash commands synced successfully")
        except Exception as e:
            logging.error(f"[Router] Failed to sync slash commands: {e}")

async def setup(bot):
    await bot.add_cog(RouterCog(bot))
