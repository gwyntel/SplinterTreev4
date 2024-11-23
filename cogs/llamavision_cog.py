import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json

class LlamaVisionCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="LlamaVision",
            nickname="LlamaVision",
            trigger_words=['llamavision', 'vision', 'image', 'describe this image'],
            model="openpipe:groq/llama-3.2-90b-vision-preview",
            provider="openpipe",
            prompt_file="llamavision_prompts",
            supports_vision=True
        )
        logging.debug(f"[LlamaVision] Initialized with raw_prompt: {self.raw_prompt}")
        logging.debug(f"[LlamaVision] Using provider: {self.provider}")
        logging.debug(f"[LlamaVision] Vision support: {self.supports_vision}")

        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[LlamaVision] Failed to load temperatures.json: {e}")
            self.temperatures = {}

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return "LlamaVision"

    def get_temperature(self):
        """Get temperature setting for this agent"""
        return self.temperatures.get(self.name.lower(), 0.7)
    async def generate_response(self, message):
        """Generate a response using openrouter"""
        try:
            # Format system prompt
            formatted_prompt = self.format_prompt(message)
            messages = [{"role": "system", "content": formatted_prompt}]

            # Get last 50 messages from database, excluding current message
            channel_id = str(message.channel.id)
            history_messages = await self.context_cog.get_context_messages(
                channel_id, 
                limit=50,
                exclude_message_id=str(message.id)
            )
            
            # Format history messages with proper roles
            for msg in history_messages:
                role = "assistant" if msg['is_assistant'] else "user"
                content = msg['content']
                
                # Handle system summaries
                if msg['user_id'] == 'SYSTEM' and content.startswith('[SUMMARY]'):
                    role = "system"
                    content = content[9:].strip()  # Remove [SUMMARY] prefix
                
                messages.append({
                    "role": role,
                    "content": content
                })

            # Add the current message
            messages.append({
                "role": "user",
                "content": message.content
            })

            logging.debug(f"[LlamaVision] Sending {len(messages)} messages to API")
            logging.debug(f"[LlamaVision] Formatted prompt: {formatted_prompt}")

            # Get temperature for this agent
            temperature = self.get_temperature()
            logging.debug(f"[LlamaVision] Using temperature: {temperature}")

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
                prompt_file="llamavision_prompts"
            )

            return response_stream

        except Exception as e:
            logging.error(f"Error processing message for LlamaVision: {e}")
            return None
async def setup(bot):
    try:
        cog = LlamaVisionCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[LlamaVision] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[LlamaVision] Failed to register cog: {e}", exc_info=True)
        raise