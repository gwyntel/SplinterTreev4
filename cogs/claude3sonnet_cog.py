import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
from shared.utils import log_interaction, analyze_emotion
import time

class Claude3SonnetCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Claude-3.5-Sonnet",
            nickname="Claude-3.5-Sonnet",
            trigger_words=['sonnet', 'claude3sonnet', 'claude 3 sonnet'],
            model="anthropic/claude-3.5-sonnet:beta",
            provider="openrouter",
            prompt_file="consolidated_prompts",
            supports_vision=True
        )
        self.context_cog = bot.get_cog('ContextCog')
        logging.debug(f"[{self.name}] Initialized with raw_prompt: {self.raw_prompt}")
        logging.debug(f"[{self.name}] Using provider: {self.provider}")
        logging.debug(f"[{self.name}] Vision support: {self.supports_vision}")

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return self.name

    async def generate_response(self, message):
        """Generate a response using OpenRouter"""
        try:
            # Use system prompt directly from base_cog
            messages = [{"role": "system", "content": self.raw_prompt}]

            # Add current message with any image descriptions
            if message.attachments:
                # Get alt text for this message
                alt_text = await self.context_cog.get_alt_text(str(message.id))
                if alt_text:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": message.content},
                            {"type": "text", "text": f"Image description: {alt_text}"}
                        ]
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": message.content
                    })
            else:
                messages.append({
                    "role": "user",
                    "content": message.content
                })

            logging.debug(f"[{self.name}] Sending {len(messages)} messages to API")
            logging.debug(f"[{self.name}] System prompt: {self.raw_prompt}")

            # Get temperature from base_cog
            temperature = self.get_temperature()
            logging.debug(f"[{self.name}] Using temperature: {temperature}")

            # Call OpenRouter API and return the stream directly
            response_stream = await self.api_client.call_openrouter(
                messages=messages,
                model=self.model,
                temperature=temperature,
                stream=True
            )

            return response_stream

        except Exception as e:
            logging.error(f"Error processing message for {self.name}: {str(e)}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle incoming messages"""
        if message.author == self.bot.user:
            return

        # Let base_cog handle message processing
        await super().handle_message(message)

async def setup(bot):
    try:
        cog = Claude3SonnetCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[{cog.name}] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[{cog.name}] Failed to register cog: {str(e)}", exc_info=True)
        raise
