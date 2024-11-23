import discord
from discord.ext import commands
import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from textblob import TextBlob
from shared.api import api
from .base_cog import BaseCog

class RouterCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Router",
            nickname="Router",
            trigger_words=[],
            model="openpipe:openrouter/openai/gpt-4o-2024-11-20",
            provider="openpipe",
            prompt_file="router",
            supports_vision=False
        )
        self.db_path = 'databases/user_settings.db'
        self.start_time = datetime.now(timezone.utc)
        self.activated_channels = self._load_activated_channels()
        # Load the system prompt
        self.router_system_prompt = self._load_router_system_prompt()
        # Start command syncing task
        self.sync_task = None
        
        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[Router] Failed to load temperatures.json: {e}")
            self.temperatures = {}

        # Map of model name variations to correct cog names
        self.model_name_map = {
            'gpt4o': 'GPT4O',
            'gpt-4o': 'GPT4O',
            'gpt4': 'GPT4O',
            'gpt-4': 'GPT4O',
            'claude3haiku': 'Claude3Haiku',
            'claude3': 'Claude3Haiku',
            'claude': 'Claude3Haiku',
            'llamavision': 'LlamaVision',
            'llama': 'LlamaVision',
            'vision': 'LlamaVision'
        }

    def get_temperature(self):
        """Get temperature setting for this agent"""
        return self.temperatures.get(self.name.lower(), 0.7)

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

    def _get_uptime(self) -> str:
        """Calculate and format the bot's uptime"""
        now = datetime.now(timezone.utc)
        delta = now - self.start_time
        
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            
        return ", ".join(parts)

    def _normalize_model_name(self, name: str) -> str:
        """Normalize model name to correct cog name format"""
        # Remove non-alphanumeric characters and convert to lowercase
        clean_name = ''.join(c for c in name if c.isalnum()).lower()
        
        # Check if we have a mapping for this name
        if clean_name in self.model_name_map:
            return self.model_name_map[clean_name]
            
        # If no mapping exists, capitalize first letter of each word
        return ''.join(word.capitalize() for word in clean_name.split())

    def analyze_sentiment(self, text: str) -> tuple:
        """
        Analyze the sentiment of a message using TextBlob.
        Returns (polarity, subjectivity) where:
        - polarity is between -1 (negative) and 1 (positive)
        - subjectivity is between 0 (objective) and 1 (subjective)
        """
        try:
            analysis = TextBlob(text)
            return analysis.sentiment.polarity, analysis.sentiment.subjectivity
        except Exception as e:
            logging.error(f"[Router] Error analyzing sentiment: {str(e)}")
            return 0.0, 0.0

    async def cog_check(self, ctx):
        """Check if user has permission to use commands in this context"""
        # Allow all commands in DM channels
        if isinstance(ctx.channel, discord.DMChannel):
            return True
        # Require manage_channels permission in guild channels
        return ctx.author.guild_permissions.manage_channels

    @commands.hybrid_command(name="uptime", description="Display bot's uptime")
    async def uptime(self, ctx):
        """Display how long the bot has been running"""
        uptime_str = self._get_uptime()
        await ctx.send(f"🕒 Bot has been running for: {uptime_str}")

    @commands.hybrid_command(name="activate", description="Activate router in this channel")
    async def activate(self, ctx):
        """Activate the router in the current channel"""
        channel_id = str(ctx.channel.id)
        
        if isinstance(ctx.channel, discord.DMChannel):
            if 'DM' not in self.activated_channels:
                self.activated_channels['DM'] = {}
            self.activated_channels['DM'][channel_id] = True
            self._save_activated_channels(self.activated_channels)
            await ctx.send("✅ Router activated in this DM channel")
        else:
            guild_id = str(ctx.guild.id)
            if guild_id not in self.activated_channels:
                self.activated_channels[guild_id] = {}
            self.activated_channels[guild_id][channel_id] = True
            self._save_activated_channels(self.activated_channels)
            await ctx.send("✅ Router activated in this channel")

    @commands.hybrid_command(name="deactivate", description="Deactivate router in this channel")
    async def deactivate(self, ctx):
        """Deactivate the router in the current channel"""
        channel_id = str(ctx.channel.id)
        
        if isinstance(ctx.channel, discord.DMChannel):
            if 'DM' in self.activated_channels and channel_id in self.activated_channels['DM']:
                del self.activated_channels['DM'][channel_id]
                if not self.activated_channels['DM']:  # Remove DM dict if empty
                    del self.activated_channels['DM']
                self._save_activated_channels(self.activated_channels)
                await ctx.send("✅ Router deactivated in this DM channel")
            else:
                await ctx.send("❌ Router is not activated in this DM channel")
        else:
            guild_id = str(ctx.guild.id)
            if guild_id in self.activated_channels and channel_id in self.activated_channels[guild_id]:
                del self.activated_channels[guild_id][channel_id]
                if not self.activated_channels[guild_id]:  # Remove guild dict if empty
                    del self.activated_channels[guild_id]
                self._save_activated_channels(self.activated_channels)
                await ctx.send("✅ Router deactivated in this channel")
            else:
                await ctx.send("❌ Router is not activated in this channel")

    async def handle_message(self, message):
        """Route the message to the appropriate cog based on the model's decision."""
        try:
            channel_id = str(message.channel.id)
            is_dm = isinstance(message.channel, discord.DMChannel)

            # Check if channel is activated
            if is_dm:
                if 'DM' not in self.activated_channels:
                    logging.info("[Router] DM channel not activated.")
                    return  # DM not activated
                if channel_id not in self.activated_channels['DM']:
                    logging.info("[Router] DM channel not activated.")
                    return  # DM not activated
            else:
                guild_id = str(message.guild.id) if message.guild else None
                if not guild_id or guild_id not in self.activated_channels or channel_id not in self.activated_channels[guild_id]:
                    logging.info("[Router] Guild channel not activated.")
                    return  # Channel not activated

            # Analyze message sentiment
            polarity, subjectivity = self.analyze_sentiment(message.content)
            logging.info(f"[Router] Message sentiment - Polarity: {polarity}, Subjectivity: {subjectivity}")

            # Route to Hermes if sentiment is very negative (polarity < -0.5)
            if polarity < -0.5 and subjectivity > 0.5:
                logging.info("[Router] Routing to Hermes due to negative sentiment")
                cog = self.bot.get_cog("HermesCog")
                if cog and hasattr(cog, 'handle_message'):
                    await cog.handle_message(message)
                    return

            # Prepare the system prompt
            system_prompt = self.router_system_prompt

            # Format the system prompt with the user message and sentiment
            context = f"Sentiment Analysis - Polarity: {polarity}, Subjectivity: {subjectivity}"
            formatted_prompt = system_prompt.replace("{user_message}", message.content).replace("{context}", context)

            # Prepare messages for the model
            messages = [
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": message.content}
            ]

            try:
                # Start typing indicator
                async with message.channel.typing():
                    # Call the routing model with streaming enabled
                    response_stream = await self.api_client.call_openpipe(
                        messages=messages,
                        model=self.model,
                        temperature=self.get_temperature(),
                        stream=True,
                        user_id=str(message.author.id),
                        guild_id=str(message.guild.id) if message.guild else None,
                        prompt_file=self.prompt_file,
                        model_cog=self.name
                    )

                    # Process the streaming response
                    routing_response = ""
                    async for chunk in response_stream:
                        if chunk:
                            routing_response += chunk

                    # Debugging: Log the raw routing response
                    logging.debug(f"[Router] Raw routing response: {routing_response}")

                    # Clean up the response to get the cog name
                    cog_name = routing_response.strip().split('\n')[0].strip()
                    cog_name = self._normalize_model_name(cog_name)
                    logging.info(f"[Router] Normalized cog name: {cog_name}")

                    # Attempt to get the cog
                    cog_name = cog_name + "Cog"
                    logging.info(f"[Router] Looking for cog: {cog_name}")
                    cog = self.bot.get_cog(cog_name)
                    
                    if cog and hasattr(cog, 'handle_message'):
                        logging.info(f"[Router] Found cog {cog_name}, forwarding message")
                        # Forward the message to the cog
                        await cog.handle_message(message)
                    else:
                        logging.error(f"[Router] Cog '{cog_name}' not found or 'handle_message' not implemented")
                        await message.channel.send("❌ Unable to route message to the appropriate module.")

            except ValueError as e:
                # Handle specific API response structure errors
                logging.error(f"[Router] API response structure error: {str(e)}")
                await message.channel.send("❌ An error occurred while processing your message. The service may be temporarily unavailable.")
            except Exception as e:
                # Handle other API errors
                logging.error(f"[Router] API error: {str(e)}")
                await message.channel.send("❌ An error occurred while processing your message. Please try again later.")

        except Exception as e:
            logging.error(f"[Router] Error routing message: {str(e)}")
            await message.channel.send("❌ An error occurred while processing your message.")

    async def cog_load(self):
        """Called when the cog is loaded. Start command syncing."""
        await super().cog_load()
        logging.info("[Router] Cog loaded and commands synced successfully.")

async def setup(bot):
    await bot.add_cog(RouterCog(bot))
