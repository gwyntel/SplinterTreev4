import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json

class UnslopCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Unslop",
            nickname="Unslop",
            trigger_words=['unslop', 'unslopnemo'],
            model="openpipe:infermatic/TheDrummer-UnslopNemo-12B-v4.1",
            provider="openpipe",
            prompt_file="unslop_prompts",
            supports_vision=False
        )
        logging.debug(f"[Unslop] Initialized with raw_prompt: {self.raw_prompt}")
        logging.debug(f"[Unslop] Using provider: {self.provider}")
        logging.debug(f"[Unslop] Vision support: {self.supports_vision}")

        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[Unslop] Failed to load temperatures.json: {e}")
            self.temperatures = {}

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return "Unslop"

    def get_temperature(self):
        """Get temperature setting for this agent"""
        return self.temperatures.get(self.name.lower(), 0.7)

    def _format_messages(self, history_messages, current_message):
        """Format messages to ensure proper role alternation"""
        formatted_messages = []
        last_role = None
        
        # Start with system message if we have a prompt
        if self.raw_prompt:
            formatted_messages.append({
                "role": "system",
                "content": self.format_prompt(current_message)
            })
            last_role = "system"

        # Process history messages
        for msg in history_messages:
            role = "assistant" if msg['is_assistant'] else "user"
            content = msg['content']

            # Handle system summaries
            if msg['user_id'] == 'SYSTEM' and content.startswith('[SUMMARY]'):
                if last_role != "system":  # Only add if not immediately after another system message
                    formatted_messages.append({
                        "role": "system",
                        "content": content[9:].strip()  # Remove [SUMMARY] prefix
                    })
                    last_role = "system"
                continue

            # Skip if this would create two messages with the same role in a row
            if role == last_role:
                continue

            formatted_messages.append({
                "role": role,
                "content": content
            })
            last_role = role

        # Add the current message if it wouldn't create consecutive user messages
        if last_role != "user":
            formatted_messages.append({
                "role": "user",
                "content": current_message.content
            })

        return formatted_messages

    async def generate_response(self, message):
        """Generate a response using openrouter"""
        try:
            # Get last 50 messages from database, excluding current message
            channel_id = str(message.channel.id)
            history_messages = await self.context_cog.get_context_messages(
                channel_id, 
                limit=50,
                exclude_message_id=str(message.id)
            )
            
            # Format messages ensuring proper role alternation
            messages = self._format_messages(history_messages, message)

            logging.debug(f"[Unslop] Sending {len(messages)} messages to API")
            for msg in messages:
                logging.debug(f"[Unslop] Message role: {msg['role']}, content: {msg['content'][:50]}...")

            # Get temperature for this agent
            temperature = self.get_temperature()
            logging.debug(f"[Unslop] Using temperature: {temperature}")

            # Get user_id and guild_id
            user_id = str(message.author.id)
            guild_id = str(message.guild.id) if message.guild else None

            # Call API and return the stream directly
            response_stream = await self.api_client.call_openpipe(
                messages=messages,
                model=self.model,
                temperature=temperature,
                stream=True,
                provider="openpipe",
                user_id=user_id,
                guild_id=guild_id,
                prompt_file="unslop_prompts"
            )

            return response_stream

        except Exception as e:
            logging.error(f"Error processing message for Unslop: {e}")
            return None

async def setup(bot):
    try:
        cog = UnslopCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[Unslop] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[Unslop] Failed to register cog: {e}", exc_info=True)
        raise
