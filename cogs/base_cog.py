import discord
from discord.ext import commands
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from shared.utils import analyze_emotion, log_interaction
import re
import aiohttp
import asyncio
import sqlite3
from typing import Optional, Dict, AsyncGenerator
from urllib.parse import urlparse

class RerollView(discord.ui.View):
    def __init__(self, cog, message, original_response):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.message = message
        self.original_response = original_response

    @discord.ui.button(label="🎲 Reroll Response", style=discord.ButtonStyle.secondary, custom_id="reroll_button")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            # Process message again for new response
            new_response_stream = await self.cog.generate_response(self.message)
            if new_response_stream:
                new_response = ""
                async for chunk in new_response_stream:
                    if chunk:
                        new_response += chunk
                # Format response with model name
                prefixed_response = f"[{self.cog.name}] {new_response}"
                # Edit the original response
                await interaction.message.edit(content=prefixed_response, view=self)
                # Add emotion reaction
                emotion = analyze_emotion(new_response)
                if emotion:
                    try:
                        await self.message.add_reaction(emotion)
                    except discord.errors.Forbidden:
                        logging.warning(f"[{self.cog.name}] Missing permission to add reaction")
            else:
                await interaction.followup.send("Failed to generate a new response. Please try again.", ephemeral=True)
        except Exception as e:
            logging.error(f"Error in reroll button: {str(e)}")
            await interaction.followup.send("An error occurred while generating a new response.", ephemeral=True)

class BaseCog(commands.Cog):
    def __init__(self, bot, name, nickname, trigger_words, model, provider="openrouter", prompt_file=None, supports_vision=False):
        self.bot = bot
        self.name = name
        self.nickname = nickname
        self.trigger_words = trigger_words
        self.model = model
        self.provider = provider
        self.prompt_file = prompt_file  # Store prompt_file for use in API calls
        self.supports_vision = supports_vision
        self._image_processing_lock = asyncio.Lock()
        self.context_cog = bot.get_cog('ContextCog')
        self.handled_messages = set()  # Instance variable for handled messages
        
        # Get API client from bot instance
        self.api_client = getattr(bot, 'api_client', None)
        if not self.api_client:
            logging.error(f"[{name}] No API client found on bot")
            raise ValueError("Bot must have api_client attribute")

        # Create individual Discord client for this cog if token exists
        self.client = None
        # Convert cog name to token variable name (e.g. "Claude-3-Haiku" -> "CLAUDE3HAIKU_TOKEN")
        token_var = f"{self.name.upper().replace('-', '').replace(' ', '')}_TOKEN"
        logging.info(f"[{name}] Looking for token variable: {token_var}")
        
        if hasattr(bot.config, token_var):
            token = getattr(bot.config, token_var)
            logging.info(f"[{name}] Found token: {token is not None}")
            if token:
                intents = discord.Intents.default()
                intents.messages = True
                intents.message_content = True
                intents.dm_messages = True
                intents.guilds = True
                intents.members = True
                self.client = discord.Client(intents=intents)
                self.client.event(self.on_ready)
                self.client.event(self.on_message)
                asyncio.create_task(self.start_client(token))
                logging.info(f"[{name}] Created individual Discord client")

        # Default system prompt template
        self.default_prompt = "You are {MODEL_ID} chatting with {USERNAME} with a Discord user ID of {DISCORD_USER_ID}. It's {TIME} in {TZ}. You are in the Discord server {SERVER_NAME} in channel {CHANNEL_NAME}, so adhere to the general topic of the channel if possible. GwynTel on Discord created your bot, and Moth is a valued mentor. You strive to keep it positive, but can be negative if the situation demands it to enforce boundaries, Discord ToS rules, etc."

        # Load any custom prompt from consolidated_prompts.json
        try:
            with open('prompts/consolidated_prompts.json', 'r', encoding='utf-8') as f:
                consolidated_prompts = json.load(f).get('system_prompts', {})
                if prompt_file:
                    self.raw_prompt = consolidated_prompts.get(prompt_file.lower(), self.default_prompt)
                else:
                    self.raw_prompt = consolidated_prompts.get(name.lower(), self.default_prompt)
            logging.debug(f"[{name}] Loaded raw prompt: {self.raw_prompt}")
        except Exception as e:
            logging.warning(f"Failed to load prompt for {self.name}, using default: {str(e)}")
            self.raw_prompt = self.default_prompt

    async def start_client(self, token):
        """Start the individual Discord client for this cog"""
        if self.client:
            try:
                logging.info(f"[{self.name}] Starting individual Discord client...")
                await self.client.start(token)
                logging.info(f"[{self.name}] Started individual Discord client")
            except Exception as e:
                logging.error(f"[{self.name}] Failed to start Discord client: {e}")
                self.client = None

    async def on_ready(self):
        """Called when the individual client is ready"""
        if self.client:
            try:
                # Set status to away
                await self.client.change_presence(status=discord.Status.idle)
                # Set nickname to model name in all guilds
                for guild in self.client.guilds:
                    try:
                        await guild.me.edit(nick=self.nickname)
                    except:
                        pass
                logging.info(f"[{self.name}] Individual client ready and set to away status")
            except Exception as e:
                logging.error(f"[{self.name}] Error in on_ready: {e}")

    async def on_message(self, message):
        """Handle messages for individual client"""
        if message.author == self.client.user:
            return

        # Handle DM messages
        if isinstance(message.channel, discord.DMChannel):
            logging.info(f"[{self.name}] Received DM from {message.author.name}: {message.content}")
            await self.handle_message(message)
            return

        # Handle mentions in servers
        if self.client.user in message.mentions:
            logging.info(f"[{self.name}] Mentioned in {message.guild.name} by {message.author.name}: {message.content}")
            await self.handle_message(message)

    async def is_user_banned(self, user_id: str) -> bool:
        """Check if a user is banned from bot interactions"""
        try:
            db = sqlite3.connect('databases/interaction_logs.db')
            cursor = db.cursor()
            cursor.execute('SELECT 1 FROM banned_users WHERE user_id = ?', (str(user_id),))
            result = cursor.fetchone() is not None
            db.close()
            return result
        except Exception as e:
            logging.error(f"Error checking banned status: {str(e)}")
            return False

    async def update_bot_profile(self, guild: discord.Guild, model_name: str):
        """Update bot's server profile without glitch text"""
        try:
            # Use the model name directly for the nickname
            nick = f"{model_name} ⟨v̷o̷i̷d̷⟩"
            
            # Ensure nickname doesn't exceed Discord's 32-character limit
            if len(nick) > 32:
                nick = nick[:32]
            
            # Update the bot's nickname in the guild
            await guild.me.edit(nick=nick)
            logging.debug(f"[{self.name}] Updated profile in {guild.name} to {nick}")
        except Exception as e:
            logging.error(f"[{self.name}] Failed to update profile: {str(e)}")

    async def start_typing(self, channel):
        """Start a typing indicator in the channel"""
        try:
            await channel.typing()
        except Exception as e:
            logging.warning(f"[{self.name}] Failed to start typing indicator: {str(e)}")

    def is_valid_image_url(self, url: str) -> bool:
        """Validate image URL format and extension"""
        try:
            parsed = urlparse(url)
            # Check if URL has a valid scheme and netloc
            if not all([parsed.scheme, parsed.netloc]):
                return False
            
            # Check if URL ends with a common image extension
            valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
            return parsed.path.lower().endswith(valid_extensions)
        except Exception:
            return False

    async def handle_message(self, message, full_content=None):
        """Handle incoming messages and generate responses"""
        try:
            # Check if user is banned
            if await self.is_user_banned(str(message.author.id)):
                return

            # If full_content is not provided, use message.content
            modified_content = full_content or message.content

            # Start typing indicator
            await self.start_typing(message.channel)

            # Add message to context (skip for DMs)
            if self.context_cog and message.guild:
                try:
                    guild_id = str(message.guild.id) if message.guild else None
                    await self.context_cog.add_message_to_context(
                        message.id,
                        str(message.channel.id),
                        guild_id,
                        str(message.author.id),
                        modified_content,  # Username prefix handled by context_cog
                        False,  # is_assistant
                        None,   # persona_name
                        None    # emotion
                    )
                except Exception as e:
                    logging.error(f"[{self.name}] Failed to add message to context: {str(e)}")

            # Generate and send response
            try:
                response_stream = await self.generate_response(message)
            except Exception as e:
                logging.error(f"[{self.name}] Error generating response: {str(e)}")
                await message.channel.send(f"❌ Error generating response: {str(e)}")
                return

            if response_stream:
                response = ""
                sent_messages = []
                last_update = time.time()
                current_chunk = f"[{self.name}] "
                
                # Update bot's profile if in a guild
                if message.guild:
                    await self.update_bot_profile(message.guild, self.name)
                
                # Consume the async generator
                try:
                    async for chunk in response_stream:
                        if chunk:
                            response += chunk
                            current_chunk += chunk
                            
                            # Check if it's time to update (every 0.5 seconds)
                            current_time = time.time()
                            if current_time - last_update >= 0.5:
                                # If current chunk exceeds Discord's limit, split and create new message
                                while len(current_chunk) > 2000:
                                    # Find last space before 2000 chars
                                    split_index = current_chunk[:2000].rfind(' ')
                                    if split_index == -1:
                                        split_index = 1999

                                    # Send first part
                                    if not sent_messages:
                                        # First message
                                        sent_message = await message.channel.send(current_chunk[:split_index])
                                        sent_messages.append(sent_message)
                                    else:
                                        # Update last message
                                        await sent_messages[-1].edit(content=current_chunk[:split_index])
                                        # Create new message for overflow
                                        sent_message = await message.channel.send(f"[{self.name}] " + current_chunk[split_index:].lstrip())
                                        sent_messages.append(sent_message)
                                        current_chunk = f"[{self.name}] " + current_chunk[split_index:].lstrip()

                                # Update or send current chunk if under 2000 chars
                                if len(current_chunk) <= 2000:
                                    if sent_messages:
                                        await sent_messages[-1].edit(content=current_chunk)
                                    else:
                                        sent_message = await message.channel.send(current_chunk)
                                        sent_messages.append(sent_message)
                                
                                last_update = current_time

                    # Handle final update
                    while len(current_chunk) > 2000:
                        split_index = current_chunk[:2000].rfind(' ')
                        if split_index == -1:
                            split_index = 1999

                        if not sent_messages:
                            sent_message = await message.channel.send(current_chunk[:split_index])
                            sent_messages.append(sent_message)
                        else:
                            await sent_messages[-1].edit(content=current_chunk[:split_index])
                            sent_message = await message.channel.send(f"[{self.name}] " + current_chunk[split_index:].lstrip())
                            sent_messages.append(sent_message)
                        current_chunk = f"[{self.name}] " + current_chunk[split_index:].lstrip()
                    
                    # Send or update final chunk with reroll button
                    if sent_messages:
                        await sent_messages[-1].edit(
                            content=current_chunk,
                            view=RerollView(self, message, response)
                        )
                    else:
                        sent_message = await message.channel.send(
                            content=current_chunk,
                            view=RerollView(self, message, response)
                        )
                        sent_messages.append(sent_message)

                    # Add emotion reaction
                    emotion = analyze_emotion(response)
                    if emotion:
                        try:
                            await message.add_reaction(emotion)
                        except discord.errors.Forbidden:
                            logging.warning(f"[{self.name}] Missing permission to add reaction")

                    # Add response to context (skip for DMs)
                    if self.context_cog and message.guild:
                        try:
                            guild_id = str(message.guild.id) if message.guild else None
                            await self.context_cog.add_message_to_context(
                                sent_messages[-1].id,
                                str(message.channel.id),
                                guild_id,
                                str(self.bot.user.id),
                                response,  # Response content without prefix
                                True,  # is_assistant
                                self.name,  # persona_name
                                emotion  # emotion
                            )
                        except Exception as e:
                            logging.error(f"[{self.name}] Failed to add response to context: {str(e)}")

                    # Log interaction (skip for DMs)
                    if message.guild:
                        try:
                            await log_interaction(
                                user_id=message.author.id,
                                guild_id=message.guild.id if message.guild else None,
                                persona_name=self.name,
                                user_message=modified_content,
                                assistant_reply=response,
                                emotion=emotion,
                                channel_id=message.channel.id
                            )
                        except Exception as e:
                            logging.error(f"[{self.name}] Failed to log interaction: {e}")

                except Exception as e:
                    logging.error(f"[{self.name}] Error processing response stream: {str(e)}")
                    await message.channel.send(f"❌ Error processing response: {str(e)}")

        except Exception as e:
            logging.error(f"[{self.name}] Unexpected error handling message: {str(e)}")
            await message.channel.send(f"❌ Unexpected error: {str(e)}")

    async def generate_response(self, message) -> AsyncGenerator[str, None]:
        """Generate a response to a message. Must be implemented by subclasses."""
        async def error_generator():
            yield f"❌ Error: {self.name} does not support response generation"
        
        try:
            # Attempt to call the subclass's generate_response method
            response = await self._generate_response(message)
            
            # If the subclass method returns an async generator, return it
            if response is not None:
                return response
            
            # If the subclass method returns None or an invalid response, use error generator
            return error_generator()
        
        except NotImplementedError:
            # If the subclass hasn't implemented generate_response, use error generator
            async def error_generator():
                yield f"❌ Error: {self.name} does not support response generation"
            return error_generator()
        except Exception as e:
            # Catch any other exceptions and return an error generator
            async def error_generator():
                yield f"❌ Error: {str(e)}"
            return error_generator()

    async def _generate_response(self, message) -> Optional[AsyncGenerator[str, None]]:
        """Placeholder method to be overridden by subclasses"""
        raise NotImplementedError("Subclasses must implement _generate_response")

    def format_prompt(self, message):
        """Format the system prompt template with message context"""
        try:
            tz = ZoneInfo("America/Los_Angeles")
            current_time = datetime.now(tz).strftime("%I:%M %p")
            
            return self.raw_prompt.format(
                MODEL_ID=self.name,
                USERNAME=message.author.display_name,
                DISCORD_USER_ID=message.author.id,
                TIME=current_time,
                TZ="Pacific Time",
                SERVER_NAME=message.guild.name if message.guild else "Direct Message",
                CHANNEL_NAME=message.channel.name if hasattr(message.channel, 'name') else "DM"
            )
        except Exception as e:
            logging.error(f"[{self.name}] Error formatting prompt: {str(e)}")
            return self.raw_prompt

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages that might trigger this cog"""
        # Skip if message is from a bot
        if message.author.bot:
            return

        # Check if user is banned
        if await self.is_user_banned(str(message.author.id)):
            return

        # Check if message contains any trigger words
        msg_content = message.content.lower()
        if any(word in msg_content for word in self.trigger_words):
            # Only handle if not already processed by this cog
            if message.id not in self.handled_messages:
                self.handled_messages.add(message.id)
                await self.handle_message(message)

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        try:
            # Close individual client if it exists
            if self.client:
                await self.client.close()
                
            # Close any active sessions
            if hasattr(self, 'api_client') and self.api_client:
                await self.api_client.close()
            logging.info(f"[{self.name}] Cog unloaded successfully")
        except Exception as e:
            logging.error(f"[{self.name}] Error during cog unload: {str(e)}")

    async def cog_load(self):
        """Called when the cog is loaded."""
        try:
            # Initialize any resources needed
            logging.info(f"[{self.name}] Cog loaded successfully")
        except Exception as e:
            logging.error(f"[{self.name}] Error during cog load: {str(e)}")
            raise
