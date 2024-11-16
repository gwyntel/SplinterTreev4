import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json
from typing import AsyncGenerator, Optional, Dict, List
import re

class RouterCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Router",
            nickname="Router",
            trigger_words=[],
            model="meta-llama/llama-3.2-3b-instruct:free",
            provider="openrouter",
            prompt_file="router",
            supports_vision=False
        )
        logging.debug(f"[Router] Initialized with raw_prompt: {self.raw_prompt}")
        logging.debug(f"[Router] Using provider: {self.provider}")
        logging.debug(f"[Router] Vision support: {self.supports_vision}")

        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[Router] Failed to load temperatures.json: {e}")
            self.temperatures = {}

        # Initialize set to track active channels
        self.active_channels = set()

        # Track last model used per channel to prevent loops
        self.last_model_used = {}

        # Track handled messages to prevent duplicates
        self.handled_messages = set()

        # Keywords that should bypass the router
        self.bypass_keywords = [
            r'\b(use|switch to|try|with)\s+(dolphin|gemini|sonar|sydney|goliath|sonnet|hermes|sorcerer|llama32vision|llama32_90b|claude3haiku|gemma|inferor|liquid|llama32_11b|magnum|mixtral|nemotron|noromaid|openchat|pixtral|rplus)\b',
            r'\b(dolphin|gemini|sonar|sydney|goliath|sonnet|hermes|sorcerer|llama32vision|llama32_90b|claude3haiku|gemma|inferor|liquid|llama32_11b|magnum|mixtral|nemotron|noromaid|openchat|pixtral|rplus)\s+(please|now|instead)\b',
            r'^(dolphin|gemini|sonar|sydney|goliath|sonnet|hermes|sorcerer|llama32vision|llama32_90b|claude3haiku|gemma|inferor|liquid|llama32_11b|magnum|mixtral|nemotron|noromaid|openchat|pixtral|rplus)[,:]\s',
            r'\b(dolphin|gemini|sonar|sydney|goliath|sonnet|hermes|sorcerer|llama32vision|llama32_90b|claude3haiku|gemma|inferor|liquid|llama32_11b|magnum|mixtral|nemotron|noromaid|openchat|pixtral|rplus)\b'  # Added to catch standalone model names
         ]

        # Model mapping for routing - updated to reflect current cogs
        self.model_mapping = {
            'Claude3Haiku': 'Claude3HaikuCog',
            'Dolphin': 'DolphinCog',
            'Freerouter': 'FreerouterCog',
            'Gemini': 'GeminiCog',
            'Gemma': 'GemmaCog',
            'Goliath': 'GoliathCog',
            'Hermes': 'HermesCog',
            'Inferor': 'InferorCog',
            'Liquid': 'LiquidCog',
            'Llama32_11b': 'Llama32_11bCog',
            'Llama32_90b': 'Llama32_90bCog',
            'Magnum': 'MagnumCog',
            'Ministral': 'MinistralCog',
            'Mixtral': 'MixtralCog',
            'Nemotron': 'NemotronCog',
            'Noromaid': 'NoromaidCog',
            'Openchat': 'OpenchatCog',
            'Pixtral': 'PixtralCog',
            'Rplus': 'RplusCog',
            'Router': 'RouterCog',
            'Sonar': 'SonarCog',
            'Sonnet': 'SonnetCog',
            'Sorcerer': 'SorcererCog',
            'Sydney': 'SydneyCog'
        }

        # Create case-insensitive lookup for model names
        self.model_lookup = {k.lower(): k for k in self.model_mapping.keys()}
        logging.debug(f"[Router] Model lookup table: {self.model_lookup}")

        # Initialize user-specific store settings
        self.user_store_settings = {}

    def has_bypass_keywords(self, content: str) -> bool:
        """Check if message contains keywords that should bypass routing"""
        content = content.lower()
        for pattern in self.bypass_keywords:
            if re.search(pattern, content, re.IGNORECASE):
                logging.debug(f"[Router] Found bypass keyword pattern: {pattern}")
                return True
        return False

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return "Router"

    def get_temperature(self):
        """Get temperature setting for this agent"""
        return self.temperatures.get(self.name.lower(), 0.7)

    def has_image_attachments(self, message: discord.Message) -> bool:
        """Check if message contains image attachments"""
        if message.attachments:
            return any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)
        return False

    def should_handle_message(self, message: discord.Message) -> bool:
        """Determine if the message should be handled by the router"""
        # Never handle bot messages
        if message.author.bot:
            logging.debug(f"[Router] Ignoring bot message from {message.author.name}")
            return False

        # Never handle messages from self
        if message.author.id == self.bot.user.id:
            logging.debug("[Router] Ignoring own message")
            return False

        # Skip if message already handled
        if message.id in self.handled_messages:
            logging.debug(f"[Router] Skipping already handled message {message.id}")
            return False

        # Skip if message contains bypass keywords
        if self.has_bypass_keywords(message.content):
            logging.debug(f"[Router] Skipping message with bypass keywords: {message.content[:100]}")
            return False

        # Always handle DMs
        if isinstance(message.channel, discord.DMChannel):
            logging.debug("[Router] Handling DM")
            return True

        # Handle if bot is mentioned
        if self.bot.user in message.mentions:
            logging.debug("[Router] Handling mention")
            return True

        # Handle if channel is activated
        if message.channel.id in self.active_channels:
            logging.debug(f"[Router] Handling message in activated channel {message.channel.id}")
            return True

        logging.debug(f"[Router] Not handling message: not DM/mention/activated channel")
        return False

    def check_routing_loop(self, channel_id: int, model_name: str) -> bool:
        """Check if we're in a routing loop"""
        if channel_id in self.last_model_used:
            last_model = self.last_model_used[channel_id]
            consecutive_count = self.last_model_used.get(f"{channel_id}_count", 0)
            
            if last_model == model_name:
                consecutive_count += 1
                if consecutive_count >= 3:  # Three consecutive same routes indicates a loop
                    logging.warning(f"[Router] Detected routing loop to {model_name} in channel {channel_id}")
                    return True
            else:
                consecutive_count = 1
            
            self.last_model_used[f"{channel_id}_count"] = consecutive_count
        
        self.last_model_used[channel_id] = model_name
        return False

    def normalize_model_name(self, raw_model_name: str) -> str:
        """Normalize model name to handle case differences and variations"""
        # Clean up the raw model name
        cleaned_name = raw_model_name.strip().lower()
        
        # Log the normalization process
        logging.debug(f"[Router] Normalizing model name: '{raw_model_name}' -> '{cleaned_name}'")
        logging.debug(f"[Router] Looking up in available models: {list(self.model_lookup.keys())}")
        
        # Look up the canonical model name
        canonical_name = self.model_lookup.get(cleaned_name)
        
        if canonical_name:
            logging.info(f"[Router] Normalized '{raw_model_name}' to '{canonical_name}'")
            return canonical_name
        
        # If not found, try some common variations
        variations = {
            'ministral': 'Ministral',
            'ministeral': 'Ministral',
            'mistral': 'Ministral',
            'llama32_90b': 'Llama32_90b',
            'llama32vision': 'Llama32_90b'
        }
        if cleaned_name in variations:
            canonical_name = variations[cleaned_name]
            logging.info(f"[Router] Normalized variation '{raw_model_name}' to '{canonical_name}'")
            return canonical_name
            
        logging.warning(f"[Router] Could not normalize model name '{raw_model_name}', falling back to Ministral")
        return 'Ministral'

    async def determine_route(self, message: discord.Message) -> str:
        """Use OpenRouter inference to determine which model to route to"""
        try:
            # Check for images first
            if self.has_image_attachments(message):
                return 'Gemini'  # Default to Gemini for image processing

            # Format the routing prompt
            routing_prompt = f"""Analyze this message and route it to the most appropriate model based on content. Return ONLY the model name, no explanation.

Message: "{message.content}"

Available Models:
1. Sonar - Current events, news, updates, time-sensitive info
2. Dolphin - Uncensored topics, mature content, controversial subjects
3. Hermes - Mental health, crisis support, emotional guidance
4. Sorcerer - Fantasy roleplay, character immersion, standard RP
5. Goliath - Long-form stories, detailed plots, epic narratives
6. Sydney - Emotional support, friendship, daily life chat
7. Sonnet - Technical tasks, coding, software engineering
8. Ministral - Default for general conversation
9. Claude3Haiku - Haiku
10. Gemma - Kind, helpful, harmless
11. Inferor - Evil, harmful, unkind
12. Liquid - Short, quick responses
13. Llama32_11b - 11b llama2 model
14. Llama32_90b - 90b llama2 model with vision
15. Magnum - Long, detailed responses
16. Mixtral - Mistral 
17. Nemotron - Technical, code-focused
18. Noromaid - Roleplay, narrative focused
19. Openchat - Similar to ChatGPT
20. Pixtral - Mistral with vision
21. Rplus - Roleplay focused

Model name:"""

            # Call OpenRouter API for inference
            messages = [
                {"role": "system", "content": "You are a message routing assistant. Return only the model name."},
                {"role": "user", "content": routing_prompt}
            ]

            logging.debug(f"[Router] Calling OpenRouter API for message: {message.content[:100]}...")
            try:
                # Try with free model first
                response = await self.api_client.call_openrouter(
                    messages=messages,
                    model="meta-llama/llama-3.2-3b-instruct:free",
                    temperature=0.3,  # Low temperature for more consistent routing
                    stream=False,
                    user_id=str(message.author.id),
                    guild_id=str(message.guild.id) if message.guild else None
                )
            except Exception as e:
                logging.warning(f"[Router] Free model failed, falling back to paid model: {str(e)}")
                # Fallback to paid model
                response = await self.api_client.call_openrouter(
                    messages=messages,
                    model="meta-llama/llama-3.2-3b-instruct",
                    temperature=0.3,
                    stream=False,
                    user_id=str(message.author.id),
                    guild_id=str(message.guild.id) if message.guild else None
                )

            if response and 'choices' in response:
                raw_model_name = response['choices'][0]['message']['content'].strip()
                logging.debug(f"[Router] Raw model name from API: {raw_model_name}")
                
                # Normalize the model name
                model_name = self.normalize_model_name(raw_model_name)
                
                # Check for routing loops
                if self.check_routing_loop(message.channel.id, model_name):
                    logging.warning(f"[Router] Breaking routing loop, falling back to Ministral")
                    return 'Ministral'
                
                logging.info(f"[Router] Determined route: {model_name} for message: {message.content[:100]}...")
                return model_name

            logging.error("[Router] Invalid response format from OpenRouter")
            logging.debug(f"[Router] Full API response: {response}")
            return 'Ministral'  # Default fallback

        except Exception as e:
            logging.error(f"[Router] Error determining route: {str(e)}")
            return 'Ministral'  # Default fallback

    async def route_to_cog(self, message: discord.Message, model_name: str) -> None:
        """Route the message to the appropriate cog"""
        try:
            cog_name = self.model_mapping.get(model_name)
            if not cog_name:
                logging.error(f"[Router] No cog mapping found for model: {model_name}")
                return

            cog = self.bot.get_cog(cog_name)
            if not cog:
                logging.error(f"[Router] Cog not found: {cog_name}")
                return

            logging.info(f"[Router] Routing message to {cog_name}")
            await cog.handle_message(message)

        except Exception as e:
            logging.error(f"[Router] Error routing to cog: {str(e)}")
            await message.channel.send(f"❌ Error routing message: {str(e)}")

    @commands.command(name='activate')
    @commands.has_permissions(manage_channels=True)
    async def activate(self, ctx):
        """Activate RouterCog in the current channel."""
        channel_id = ctx.channel.id
        self.active_channels.add(channel_id)
        await ctx.send("RouterCog has been activated in this channel. All messages will now be routed to appropriate models.")
        logging.info(f"[Router] Activated in channel {channel_id}")

    @commands.command(name='deactivate')
    @commands.has_permissions(manage_channels=True)
    async def deactivate(self, ctx):
        """Deactivate RouterCog in the current channel."""
        channel_id = ctx.channel.id
        self.active_channels.discard(channel_id)
        # Clear any loop detection state
        self.last_model_used.pop(channel_id, None)
        self.last_model_used.pop(f"{channel_id}_count", None)
        await ctx.send("RouterCog has been deactivated in this channel.")
        logging.info(f"[Router] Deactivated in channel {channel_id}")

    @commands.command(name='store')
    async def toggle_store(self, ctx, option: str):
        """Toggle the store setting for the user. Use '!store on' to enable and '!store off' to disable."""
        user_id = ctx.author.id
        if option.lower() == 'on':
            self.user_store_settings[user_id] = True
            await ctx.send("Store setting enabled for you.")
        elif option.lower() == 'off':
            self.user_store_settings[user_id] = False
            await ctx.send("Store setting disabled for you.")
        else:
            await ctx.send("Invalid option. Use '!store on' or '!store off'.")

    def is_store_enabled(self, user_id: int) -> bool:
        """Check if the store setting is enabled for a user."""
        return self.user_store_settings.get(user_id, False)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle all incoming messages"""
        # Skip if message is from a bot
        if message.author.bot:
            logging.debug(f"[Router] Ignoring bot message from {message.author.name}")
            return

        # Skip if message is a command
        if message.content.startswith('!'):
            return

        # Check if we should handle this message
        if not self.should_handle_message(message):
            return

        try:
            # Mark message as handled
            self.handled_messages.add(message.id)

            # Log message details for debugging
            channel_type = "DM" if isinstance(message.channel, discord.DMChannel) else "guild"
            logging.debug(f"[Router] Processing message: channel_type={channel_type}, "
                        f"channel_id={message.channel.id}, "
                        f"author={message.author.name}, "
                        f"content={message.content[:100]}...")

            # Determine which model to route to
            model_name = await self.determine_route(message)
            logging.info(f"[Router] Determined route: {model_name} for message: {message.content[:100]}...")

            # Route the message to the appropriate cog
            await self.route_to_cog(message, model_name)

        except Exception as e:
            logging.error(f"[Router] Error handling message: {str(e)}")
            await message.channel.send(f"❌ Error processing message: {str(e)}")

    async def cog_check(self, ctx):
        """Ensure that commands are only used in guilds, except for the 'store' command."""
        if ctx.command.name == 'store':
            return True  # Allow 'store' command in DMs
        return ctx.guild is not None

async def setup(bot):
    try:
        cog = RouterCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[Router] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[Router] Failed to register cog: {e}", exc_info=True)
        raise
