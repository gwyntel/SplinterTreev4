import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json

class GoliathCog(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="Goliath",
            nickname="Goliath",
            trigger_words=['120b', 'goliath'],
            model="alpindale/goliath-120b",
            provider="openrouter",
            prompt_file="goliath_prompts",
            supports_vision=False
        )
        logging.debug(f"[Goliath] Initialized with raw_prompt: {self.raw_prompt}")
        logging.debug(f"[Goliath] Using provider: {self.provider}")
        logging.debug(f"[Goliath] Vision support: {self.supports_vision}")

        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[Goliath] Failed to load temperatures.json: {e}")
            self.temperatures = {}

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return "Goliath"

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

            # Process current message and any images
            content = []
            has_images = False
            
            # Add any image attachments
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    has_images = True
                    content.append({
                        "type": "image_url",
                        "image_url": { "url": attachment.url }
                    })

            # Check for image URLs in embeds
            for embed in message.embeds:
                if embed.image and embed.image.url:
                    has_images = True
                    content.append({
                        "type": "image_url",
                        "image_url": { "url": embed.image.url }
                    })
                if embed.thumbnail and embed.thumbnail.url:
                    has_images = True
                    content.append({
                        "type": "image_url",
                        "image_url": { "url": embed.thumbnail.url }
                    })

            # Add the text content
            content.append({
                "type": "text",
                "text": "Please describe this image in detail." if has_images else message.content
            })

            # Add the message with multimodal content
            messages.append({
                "role": "user",
                "content": content
            })

            logging.debug(f"[Goliath] Sending {len(messages)} messages to API")
            logging.debug(f"[Goliath] Formatted prompt: {formatted_prompt}")
            logging.debug(f"[Goliath] Has images: {has_images}")

            # Get temperature for this agent
            temperature = self.get_temperature()
            logging.debug(f"[Goliath] Using temperature: {temperature}")

            # Get user_id and guild_id
            user_id = str(message.author.id)
            guild_id = str(message.guild.id) if message.guild else None

            # Call API and return the stream directly
            response_stream = await self.api_client.call_openpipe(
                messages=messages,
                model=self.model,
                temperature=temperature,
                stream=True,
                provider="openrouter",
                user_id=user_id,
                guild_id=guild_id,
                prompt_file=self.prompt_file
            )

            return response_stream

        except Exception as e:
            logging.error(f"Error processing message for Goliath: {e}")
            return None

async def setup(bot):
    # Register the cog with its proper name
    try:
        cog = GoliathCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[Goliath] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[Goliath] Failed to register cog: {e}", exc_info=True)
        raise