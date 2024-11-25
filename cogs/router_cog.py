import discord
from discord.ext import commands
import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from textblob import TextBlob
from shared.api import api
from .base_cog import BaseCog
import xml.etree.ElementTree as ET

class RouterCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Router",
            nickname="Router",
            trigger_words=[],
            model="openpipe:openrouter/mistralai/ministral-8b",
            provider="openpipe",
            prompt_file="router",
            supports_vision=False
        )
        self.db_path = 'databases/user_settings.db'
        self.start_time = datetime.now(timezone.utc)
        self.activated_channels = self._load_activated_channels()
        self.router_system_prompt = self._load_router_system_prompt()
        self.api_client = api
        
        # Message tracking to prevent multiple responses
        self.handled_messages = set()
        
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
            'vision': 'LlamaVision',
            'hermes': 'Hermes',
            'grok': 'Grok',
            'sonar': 'Sonar',
            'wizard': 'Wizard',
            'qwen': 'Qwen',
            'unslop': 'Unslop',
            'rocinante': 'Rocinante',
            'sorcerer': 'Sorcerer',
            'nemotron': 'Nemotron',
            'magnum': 'Magnum',
            'inferor': 'Inferor',
            'sydney': 'SYDNEY-COURT',
            'sydney-court': 'SYDNEY-COURT',
            'sydneycourt': 'SYDNEY-COURT'
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

    def _extract_model_name(self, response: str) -> str:
        """Extract model name from response with better error handling"""
        try:
            # Check if response contains XML tags
            if '<' in response and '>' in response:
                try:
                    root = ET.fromstring(response)
                    model_tag = root.find('modelCog')
                    if model_tag is not None:
                        return model_tag.text.strip()
                except ET.ParseError:
                    logging.warning("[Router] Failed to parse XML response")
                    
            # Clean up the response
            clean_response = response.strip().lower()
            
            # Remove common prefixes/suffixes that might be added
            prefixes = ['i recommend', 'use', 'route to', 'the best model is', 'model:', 'cog:', 'using']
            for prefix in prefixes:
                if clean_response.startswith(prefix):
                    clean_response = clean_response[len(prefix):].strip()
            
            # Get the first word/line as the model name
            model_name = clean_response.split('\n')[0].split()[0].strip()
            
            # Remove any remaining punctuation
            model_name = ''.join(c for c in model_name if c.isalnum() or c.isspace() or c == '-')
            
            logging.info(f"[Router] Extracted model name: {model_name} from response: {response}")
            return model_name
        except Exception as e:
            logging.error(f"[Router] Error extracting model name: {str(e)}")
            return 'gpt4o'  # Default to GPT4O on error

    def _normalize_model_name(self, name: str) -> str:
        """Normalize model name to correct cog name format"""
        try:
            # Extract model name from potentially longer response
            name = self._extract_model_name(name)
            
            # Remove non-alphanumeric characters and convert to lowercase
            clean_name = ''.join(c.lower() for c in name if c.isalnum() or c.isspace() or c == '-').strip()
            
            # Check if we have a mapping for this name
            if clean_name in self.model_name_map:
                return self.model_name_map[clean_name]
                
            # If no mapping exists, try to find a partial match
            for key, value in self.model_name_map.items():
                if key in clean_name or clean_name in key:
                    return value
                    
            # Default to GPT4O if no match found
            return 'GPT4O'
        except Exception as e:
            logging.error(f"[Router] Error normalizing model name: {str(e)}")
            return 'GPT4O'

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
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("✅ Router is always active in DM channels")
            return
            
        channel_id = str(ctx.channel.id)
        guild_id = str(ctx.guild.id)
        if guild_id not in self.activated_channels:
            self.activated_channels[guild_id] = {}
        self.activated_channels[guild_id][channel_id] = True
        self._save_activated_channels(self.activated_channels)
        await ctx.send("✅ Router activated in this channel")

    @commands.hybrid_command(name="deactivate", description="Deactivate router in this channel")
    async def deactivate(self, ctx):
        """Deactivate the router in the current channel"""
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("❌ Router cannot be deactivated in DM channels")
            return
            
        channel_id = str(ctx.channel.id)
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
        """Legacy method to maintain compatibility with tests"""
        await self.route_message(message)

    async def route_message(self, message):
        """Route the message to the appropriate cog based on the model's decision."""
        try:
            # Check if message has already been handled
            if message.id in self.handled_messages:
                logging.info(f"[Router] Message {message.id} already handled, skipping")
                return
            
            # Mark message as handled
            self.handled_messages.add(message.id)
            
            # Clean up old message IDs (keep last 1000)
            if len(self.handled_messages) > 1000:
                self.handled_messages = set(list(self.handled_messages)[-1000:])

            # Analyze message sentiment
            polarity, subjectivity = self.analyze_sentiment(message.content)
            logging.info(f"[Router] Message sentiment - Polarity: {polarity}, Subjectivity: {subjectivity}")

            # Format the system prompt with the user message and sentiment
            context = f"Sentiment Analysis - Polarity: {polarity}, Subjectivity: {subjectivity}"
            formatted_prompt = self.router_system_prompt.replace("{user_message}", message.content).replace("{context}", context)

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

                    # Clean up the response to get the cog name
                    cog_name = self._normalize_model_name(routing_response)
                    logging.info(f"[Router] Raw response: {routing_response}")
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
                        # Default to GPT4O if cog not found
                        fallback_cog = self.bot.get_cog("GPT4OCog")
                        if fallback_cog and hasattr(fallback_cog, 'handle_message'):
                            logging.info("[Router] Falling back to GPT4OCog")
                            await fallback_cog.handle_message(message)
                        else:
                            await message.channel.send("❌ Unable to route message to the appropriate module.")

            except ValueError as e:
                logging.error(f"[Router] API response structure error: {str(e)}")
                await message.channel.send("❌ An error occurred while processing your message. The service may be temporarily unavailable.")
            except Exception as e:
                logging.error(f"[Router] API error: {str(e)}")
                await message.channel.send("❌ An error occurred while processing your message. Please try again later.")

        except Exception as e:
            logging.error(f"[Router] Error routing message: {str(e)}")
            await message.channel.send("❌ An error occurred while processing your message.")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle incoming messages"""
        # Ignore messages from bots
        if message.author.bot:
            return

        # Check if message has already been handled
        if message.id in self.handled_messages:
            return

        # Always process DMs
        is_dm = isinstance(message.channel, discord.DMChannel)
        if is_dm:
            await self.route_message(message)
            return

        # Check if message mentions the bot
        is_mention = self.bot.user in message.mentions
        if is_mention:
            await self.route_message(message)
            return

        # Check if channel is activated for guild messages
        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id)
        if guild_id in self.activated_channels and channel_id in self.activated_channels[guild_id]:
            # Check for specific keywords that would trigger other cogs
            for cog in self.bot.cogs.values():
                if hasattr(cog, 'trigger_words') and any(word.lower() in message.content.lower() for word in cog.trigger_words):
                    return  # Let other cogs handle their specific triggers
            await self.route_message(message)

    async def cog_load(self):
        """Called when the cog is loaded."""
        await super().cog_load()
        logging.info("[Router] Cog loaded and commands synced successfully.")

async def setup(bot):
    await bot.add_cog(RouterCog(bot))
