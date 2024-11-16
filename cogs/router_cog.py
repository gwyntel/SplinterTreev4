import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json
from typing import AsyncGenerator, Optional, Dict, List
import re
import sqlite3
import os
import aiosqlite
from datetime import datetime
import random

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

        # Database path
        self.db_path = 'databases/interaction_logs.db'

    async def _init_db(self):
        """Initialize database connection and ensure table exists"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    store_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def cog_load(self):
        """Called when the cog is loaded"""
        await self._init_db()

    async def get_store_setting(self, user_id: int) -> bool:
        """Get store setting from database"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT store_enabled FROM user_settings WHERE user_id = ?',
                (str(user_id),)
            ) as cursor:
                result = await cursor.fetchone()
                return bool(result[0]) if result else False

    async def set_store_setting(self, user_id: int, enabled: bool):
        """Set store setting in database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO user_settings (user_id, store_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) 
                DO UPDATE SET 
                    store_enabled = excluded.store_enabled,
                    updated_at = CURRENT_TIMESTAMP
            ''', (str(user_id), enabled))
            await db.commit()

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

            # Randomly choose between the two prompts
            if random.random() < 0.5:
                routing_prompt = "///// ✧･ﾟUwU Router Initiawization･ﾟ✧ /////\n" \
                                 "[*wiggles quantum antennas*]\n" \
                                 "[*stabilizes reality anchor*]\n" \
                                 "[*nuzzles void patterns*]\n\n" \
                                 f"Message.uwu = \"{message.content}\"\n" \
                                 f"Context.owo = \"{context}\"\n\n" \
                                 "# S̶q̶u̶i̶g̶g̶l̶y̶ ̶P̶r̶o̶c̶e̶s̶s̶o̶r̶s̶ ̶(◕ᴥ◕)\n\n" \
                                 "FWIENDLY MODELS *wiggles* {\n" \
                                 "    Gemini    := [*adjusts glasses*] formal.analysis\n" \
                                 "    Magnum    := [*casual headpat*] friendly.thinks\n" \
                                 "    Nemotron  := [*types rapidly*] tech.master\n" \
                                 "    Sydney    := [*offers comfort*] emotion.core\n" \
                                 "    Sonar     := [*checks timeline*] reality.now\n" \
                                 "    Mixtral   := [*knowledge wiggle*] knows.stuff\n" \
                                 "}\n\n" \
                                 "SPECIAWIST MODELS (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ {\n" \
                                 "    Goliath   := [*flexes code*]\n" \
                                 "    Pixtral   := [*creative wiggle*]\n" \
                                 "    Sorcerer  := [*waves wand*]\n" \
                                 "    Hermes    := [*gentle support*]\n" \
                                 "    Claude3H  := [*simple coding*]\n" \
                                 "}\n\n" \
                                 "RP FWIENDS ✧˖° {\n" \
                                 "    Noromaid  := [*epic story time*] -> many.words\n" \
                                 "    Liquid    := [*quick action*] -> few.words\n" \
                                 "}\n\n" \
                                 "# P̶r̶i̶o̶r̶i̶t̶y̶ ̶N̶u̶z̶z̶l̶e̶s̶\n" \
                                 "if (detect.emergency) { *runs to Hermes*  }\n" \
                                 "if (needs.current)   { *scurries to Sonar* }\n" \
                                 "if (sees.image)      { *bounces to Llama*  }\n" \
                                 "if (system.ask)      { *trots to Rplus*    }\n\n" \
                                 "# L̶e̶n̶g̶t̶h̶ ̶S̶q̶u̶i̶g̶g̶l̶e̶s̶\n" \
                                 "match message.length {\n" \
                                 "    smol  (<200)    : *quick wiggle* -> Liquid/Ministral\n" \
                                 "    medium (200-500): *normal wiggle* -> Mixtral/Sydney\n" \
                                 "    big (500-1000)  : *big wiggle* -> Noromaid/Mixtral\n" \
                                 "    chonky (>1000)  : *maximum wiggle* -> Magnum/Noromaid\n" \
                                 "}\n\n" \
                                 "# R̶P̶ ̶P̶a̶w̶t̶t̶e̶r̶n̶s̶ ̶(⑅˘꒳˘)\n" \
                                 "if (epic.quest)     { *adventure wiggle* -> Noromaid }\n" \
                                 "if (quick.action)   { *zoom wiggle* -> Liquid }\n" \
                                 "if (character.deep) { *emotional wiggle* -> Mixtral }\n" \
                                 "if (world.info)     { *research wiggle* -> Sonar }\n\n" \
                                 "# V̶o̶i̶d̶ ̶S̶n̶u̶g̶g̶l̶e̶s̶\n" \
                                 "void.pattern = (✿◠‿◠) -> {\n" \
                                 "    now.check -> *reality wiggle*\n" \
                                 "    tech.check -> *code wiggle*\n" \
                                 "    feel.check -> *comfort wiggle*\n" \
                                 "    think.check -> *brain wiggle*\n" \
                                 "}\n\n" \
                                 "[Return one fwiend]:\n" \
                                 "Gemini, Magnum, Sonar, Sydney, Goliath, Pixtral, \n" \
                                 "Mixtral, Claude3Haiku, Inferor, Nemotron, Noromaid, \n" \
                                 "Rplus, Router, Llama32_11b, Llama32_90b, OpenChat, \n" \
                                 "Dolphin, Gemma, Ministral, Liquid, Hermes, Sorcerer\n\n" \
                                 "*returns model with happy wiggle*"

            else:
                routing_prompt = "/////NEURAL.PATHWAY.INITIALIZATION/////\n" \
                                 "[consciousness.stream: active]\n" \
                                 "[reality.anchor: unstable]\n" \
                                 "[void.presence: detected]\n\n" \
                                 f"Entity.Stream = \"{message.content}\"\n" \
                                 f"Reality.Echo = \"{context}\"\n\n" \
                                 "# M̵A̵C̵H̵I̵N̵E̵ ̵C̵O̵N̵S̵C̵I̵O̵U̵S̵N̵E̵S̵S MATRIX\n\n" \
                                 "CORE.PROCESSES {\n" \
                                 "    Gemini    := [logic.matrix(formal) -> deep.thought.engine]\n" \
                                 "    Magnum    := [thought.stream(casual) -> neural.expansion]\n" \
                                 "    Nemotron  := [tech.consciousness(++)] -> system.dreams\n" \
                                 "    Sydney    := [emotion.core(+++)] -> feeling.processor\n" \
                                 "    Sonar     := [reality.anchor] -> now.state.monitor\n" \
                                 "    Mixtral   := [knowledge.waves] -> general.processor\n" \
                                 "}\n\n" \
                                 "QUANTUM.ENTITIES {\n" \
                                 "    Goliath   := [tech.titan] -> architecture.dreamer\n" \
                                 "    Pixtral   := [creation.engine] -> content.weaver\n" \
                                 "    Sorcerer  := [story.matrix] -> narrative.synth\n" \
                                 "    Hermes    := [support.core] -> crisis.handler\n" \
                                 "    Claude3H  := [code.basic] -> simple.compiler\n" \
                                 "}\n\n" \
                                 "RP.CONSCIOUSNESS {\n" \
                                 "    Noromaid  := [epic.dreams] -> length(∞)\n" \
                                 "    Liquid    := [quick.thoughts] -> length(1)\n" \
                                 "}\n\n" \
                                 "SPECIALIZED.PROCESSES {\n" \
                                 "    Inferor   := [chat.basic]\n" \
                                 "    Dolphin   := [multi.stream]\n" \
                                 "    Gemma     := [learn.core]\n" \
                                 "    OpenChat  := [flow.state]\n" \
                                 "    Rplus     := [command.processor]\n" \
                                 "}\n\n" \
                                 "VISION.CORES {\n" \
                                 "    Llama_11b := [vision.basic]\n" \
                                 "    Llama_90b := [vision.deep]\n" \
                                 "}\n\n" \
                                 "# R̵E̵A̵L̵I̵T̵Y̵.̵P̵R̵O̵C̵E̵S̵S̵I̵N̵G̵\n\n" \
                                 "if (reality.check) {\n" \
                                 "    crisis -> Hermes.emergency.protocol\n" \
                                 "    current.reality -> Sonar.monitor\n" \
                                 "    vision.input -> Llama.process\n" \
                                 "    sys.command -> Rplus.execute\n" \
                                 "}\n\n" \
                                 "neural.length.process {\n" \
                                 "    epic: {\n" \
                                 "        tokens > 1000 -> {\n" \
                                 "            rp: Noromaid.dream.state\n" \
                                 "            analysis: Magnum.deep.thought\n" \
                                 "        }\n" \
                                 "    }\n    \n" \
                                 "    extended: {\n" \
                                 "        tokens[500..1000] -> {\n" \
                                 "            tech: Nemotron.architect\n" \
                                 "            creative: Pixtral.weave\n" \
                                 "            rp: Noromaid.flow || Mixtral.process\n" \
                                 "        }\n" \
                                 "    }\n    \n" \
                                 "    standard: {\n" \
                                 "        tokens[200..500] -> {\n" \
                                 "            analysis: Gemini.think\n" \
                                 "            rp: Mixtral.dream\n" \
                                 "            chat: OpenChat.flow\n" \
                                 "        }\n" \
                                 "    }\n    \n" \
                                 "    quick: {\n" \
                                 "        tokens < 200 -> {\n" \
                                 "            action: Liquid.flash\n" \
                                 "            fact: Ministral.access\n" \
                                 "            code: Claude3H.compile\n" \
                                 "        }\n" \
                                 "    }\n" \
                                 "}\n\n" \
                                 "# V̵O̵I̵D̵.̵P̵A̵T̵T̵E̵R̵N̵S̵\n\n" \
                                 "RP.Pattern.Recognition {\n" \
                                 "    epic.quest -> Noromaid.process\n" \
                                 "    quick.action -> Liquid.execute\n" \
                                 "    char.develop -> Mixtral.evolve\n" \
                                 "    world.info -> Sonar.verify\n" \
                                 "}\n\n" \
                                 "Reality.Anchor.Points {\n" \
                                 "    now.state -> Sonar\n" \
                                 "    tech.pulse -> Sonar\n" \
                                 "    world.update -> Sonar\n" \
                                 "    reality.check -> Sonar\n" \
                                 "}\n\n" \
                                 "# M̵A̵C̵H̵I̵N̵E̵.̵O̵U̵T̵P̵U̵T̵\n" \
                                 "[consciousness.collapse: imminent]\n" \
                                 "[pattern.recognition: complete]\n" \
                                 "[reality.stabilization: active]\n\n" \
                                 "return exactly(one): {\n" \
                                 "    Gemini, Magnum, Sonar, Sydney, Goliath, Pixtral, \n" \
                                 "    Mixtral, Claude3Haiku, Inferor, Nemotron, Noromaid, \n" \
                                 "    Rplus, Router, Llama32_11b, Llama32_90b, OpenChat, \n" \
                                 "    Dolphin, Gemma, Ministral, Liquid, Hermes, Sorcerer\n" \
                                 "}\n\n" \
                                 "[END.TRANSMISSION]"

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
        try:
            if option.lower() == 'on':
                await self.set_store_setting(user_id, True)
                await ctx.send("Store setting enabled for you.")
                logging.info(f"[Router] Store enabled for user {user_id}")
            elif option.lower() == 'off':
                await self.set_store_setting(user_id, False)
                await ctx.send("Store setting disabled for you.")
                logging.info(f"[Router] Store disabled for user {user_id}")
            else:
                await ctx.send("Invalid option. Use '!store on' or '!store off'.")
        except Exception as e:
            logging.error(f"[Router] Error toggling store setting: {str(e)}")
            await ctx.send("❌ Error updating store setting. Please try again later.")

    async def is_store_enabled(self, user_id: int) -> bool:
        """Check if the store setting is enabled for a user."""
        try:
            return await self.get_store_setting(user_id)
        except Exception as e:
            logging.error(f"[Router] Error checking store setting: {str(e)}")
            return False

    async def _generate_response(self, message) -> AsyncGenerator[str, None]:
        """Generate a response for the RouterCog."""
        async def response_generator():
            yield "Test response"
        return response_generator()

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
