import discord
from discord.ext import commands
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from shared.utils import analyze_emotion, log_interaction, get_message_history, store_alt_text, get_alt_text, get_unprocessed_images
from shared.api import api
import re
import aiohttp
import asyncio
import tempfile

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
        self.supports_vision = supports_vision
        self._image_processing_lock = asyncio.Lock()
        self.api_client = api  # Store API client reference

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

    def is_triggered(self, message_content: str) -> bool:
        """Check if this cog should respond to the message"""
        msg_content = message_content.lower()
        # Check if message contains any of the trigger words
        return any(trigger.lower() in msg_content for trigger in self.trigger_words)

    async def generate_image_description(self, image_url):
        """Generate a description for the given image URL"""
        try:
            logging.info(f"[{self.name}] Starting image description generation for URL: {image_url}")
            
            # Construct messages for vision API with specific prompt for alt text
            messages = [
                {
                    "role": "system",
                    "content": "You are a vision model specialized in providing detailed, accurate, and concise alt text descriptions of images. Focus on the key visual elements, context, and any text present in the image. Your descriptions should be informative yet concise, suitable for screen readers."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please provide a concise but detailed alt text description of this image:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ]
            
            logging.debug(f"[{self.name}] Constructed vision API messages: {messages}")
            logging.info(f"[{self.name}] Calling OpenRouter API for vision processing")
            
            # Call API with vision capabilities
            response_data = await self.api_client.call_openrouter(messages, self.model, temperature=0.3)
            logging.debug(f"[{self.name}] Received API response: {response_data}")
            
            if response_data and 'choices' in response_data and len(response_data['choices']) > 0:
                description = response_data['choices'][0]['message']['content']
                # Clean up the description - remove any markdown or quotes
                description = description.strip('`"\' ')
                if description.lower().startswith('alt text:'):
                    description = description[8:].strip()
                logging.info(f"[{self.name}] Generated alt text: {description[:100]}...")
                return description
            else:
                logging.error(f"[{self.name}] No description generated for image - API response invalid")
                logging.debug(f"[{self.name}] Full API response: {response_data}")
                return None
                
        except Exception as e:
            logging.error(f"[{self.name}] Error generating image description: {str(e)}", exc_info=True)
            return None

    async def handle_message(self, message, full_content=None):
        """Handle incoming messages"""
        if message.author == self.bot.user:
            return

        # Only proceed if this cog is triggered by the message
        if not self.is_triggered(message.content):
            return

        logging.info(f"[{self.name}] Handling message from {message.author}: {message.content[:100]}...")
        logging.debug(f"[{self.name}] Message has {len(message.attachments)} attachments")

        # Check permissions
        permissions = message.channel.permissions_for(message.guild.me if message.guild else self.bot.user)
        can_send = permissions.send_messages if hasattr(permissions, 'send_messages') else True
        can_add_reactions = permissions.add_reactions if hasattr(permissions, 'add_reactions') else True

        if not can_send:
            logging.warning(f"[{self.name}] Missing permission to send messages in channel {message.channel.id}")
            return

        try:
            # Process images if there are any attachments
            if message.attachments:
                logging.info(f"[{self.name}] Found {len(message.attachments)} attachments")
                image_attachments = [
                    att for att in message.attachments 
                    if att.content_type and att.content_type.startswith('image/')
                ]
                logging.info(f"[{self.name}] Found {len(image_attachments)} image attachments")
                
                if image_attachments:
                    logging.info(f"[{self.name}] Starting image processing")
                    async with message.channel.typing():
                        for attachment in image_attachments:
                            try:
                                logging.debug(f"[{self.name}] Processing attachment: {attachment.filename} ({attachment.content_type})")
                                description = await self.generate_image_description(attachment.url)
                                if description:
                                    logging.info(f"[{self.name}] Generated description for {attachment.filename}")
                                    # Store alt text in database
                                    success = await store_alt_text(
                                        message_id=str(message.id),
                                        channel_id=str(message.channel.id),
                                        alt_text=description,
                                        attachment_url=attachment.url
                                    )
                                    if success:
                                        logging.info(f"[{self.name}] Successfully stored alt text for {attachment.filename}")
                                        if can_add_reactions:
                                            await message.add_reaction('🖼️')
                                    else:
                                        logging.error(f"[{self.name}] Failed to store alt text for {attachment.filename}")
                                        if can_add_reactions:
                                            await message.add_reaction('⚠️')
                                else:
                                    logging.error(f"[{self.name}] Failed to generate description for {attachment.filename}")
                                    if can_add_reactions:
                                        await message.add_reaction('❌')
                            except Exception as e:
                                logging.error(f"[{self.name}] Error processing image {attachment.filename}: {str(e)}", exc_info=True)
                                if can_add_reactions:
                                    await message.add_reaction('❌')
                                continue

            # Generate streaming response
            logging.info(f"[{self.name}] Generating streaming response")
            response_stream = await self.generate_response(message)

            if response_stream:
                # Send the streaming response
                sent_message = await self.handle_streaming_response(response_stream, message)
                if sent_message:
                    # Log interaction
                    try:
                        await log_interaction(
                            user_id=message.author.id,
                            guild_id=message.guild.id if message.guild else None,
                            persona_name=self.name,
                            user_message=message.content,
                            assistant_reply=sent_message.content,
                            emotion=analyze_emotion(sent_message.content),
                            channel_id=str(message.channel.id)
                        )
                        logging.debug(f"[{self.name}] Logged interaction for user {message.author.id}")
                    except Exception as e:
                        logging.error(f"[{self.name}] Failed to log interaction: {str(e)}")
                    return sent_message.content, None
                else:
                    logging.error(f"[{self.name}] No response received from API")
                    if can_add_reactions:
                        await message.add_reaction('❌')
                    if can_send:
                        await message.reply(f"[{self.name}] Failed to generate a response. Please try again.")
                    return None, None

        except Exception as e:
            logging.error(f"[{self.name}] Error in message handling: {str(e)}", exc_info=True)
            try:
                if can_add_reactions:
                    await message.add_reaction('❌')
                if can_send:
                    error_msg = str(e)
                    if "insufficient_quota" in error_msg.lower():
                        await message.reply("⚠️ API quota exceeded. Please try again later.")
                    elif "invalid_api_key" in error_msg.lower():
                        await message.reply("🔑 API configuration error. Please contact the bot administrator.")
                    elif "rate_limit_exceeded" in error_msg.lower():
                        await message.reply("⏳ Rate limit exceeded. Please try again later.")
                    else:
                        await message.reply(f"[{self.name}] An error occurred while processing your request.")
            except discord.errors.Forbidden:
                logging.error(f"[{self.name}] Missing permissions to send error message or add reaction")
            return None, None

    async def handle_streaming_response(self, response_stream, message):
        """Handle streaming response formatting and sending"""
        try:
            # Check permissions
            permissions = message.channel.permissions_for(message.guild.me if message.guild else self.bot.user)
            can_send = permissions.send_messages if hasattr(permissions, 'send_messages') else True
            can_dm = True  # Assume DMs are possible until proven otherwise

            if not can_send and not can_dm:
                logging.error(f"[{self.name}] No available method to send response")
                return None

            # Check if message content is spoilered using ||content|| format
            is_spoilered = message.content.startswith('||') and message.content.endswith('||')

            # Initialize response with model name prefix
            current_response = f"[{self.name}] "
            sent_message = None
            buffer = ""

            if is_spoilered:
                try:
                    # Create DM channel
                    user = message.author
                    dm_channel = await user.create_dm()
                    sent_message = await dm_channel.send(current_response)
                except discord.Forbidden:
                    logging.warning(f"Cannot send DM to user {message.author}")
                    can_dm = False
                    is_spoilered = False  # Fall back to channel message

            if not is_spoilered or (is_spoilered and not can_dm and can_send):
                sent_message = await message.reply(current_response)

            async for chunk in response_stream:
                if chunk:
                    buffer += chunk
                    sentences = re.split(r'(?<=[.!?])\s+', buffer)
                    
                    # If we have 3 or more sentences, send them
                    if len(sentences) >= 3:
                        # Join complete sentences
                        to_send = ' '.join(sentences[:-1])  # Keep the last incomplete sentence in buffer
                        buffer = sentences[-1]
                        
                        current_response += to_send + ' '
                        if len(current_response) <= 2000:
                            await sent_message.edit(content=current_response)
                        else:
                            # Create and send markdown file for long responses
                            file = await self.create_response_file(current_response, str(message.id))
                            sent_message = await message.reply(
                                f"[{self.name}] Response was too long. Full response is in the attached file:",
                                file=file
                            )
                            current_response = ""  # Reset for potential additional content

            # Send any remaining content, ensuring it ends with a complete sentence
            if buffer:
                # Check if buffer ends with sentence-ending punctuation
                if not re.search(r'[.!?]$', buffer):
                    # Wait briefly for more content that might complete the sentence
                    await asyncio.sleep(0.5)
                current_response += buffer
                if len(current_response) <= 2000:
                    await sent_message.edit(content=current_response)
                else:
                    file = await self.create_response_file(current_response, str(message.id))
                    sent_message = await message.reply(
                        f"[{self.name}] Response was too long. Full response is in the attached file:",
                        file=file
                    )

            # Add reroll view
            view = RerollView(self, message, current_response)
            await sent_message.edit(view=view)

            # Add reaction based on emotion analysis
            try:
                if permissions.add_reactions:
                    emotion = analyze_emotion(current_response)
                    if emotion:
                        await message.add_reaction(emotion)
            except Exception as e:
                logging.error(f"Error adding emotion reaction: {str(e)}")

            return sent_message

        except Exception as e:
            logging.error(f"Error sending streaming response for {self.name}: {str(e)}")
            try:
                if permissions.add_reactions:
                    await message.add_reaction('❌')
            except:
                pass
            return None

    async def create_response_file(self, response_text: str, message_id: str) -> discord.File:
        """Create a markdown file containing the response"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as temp_file:
            temp_file.write(response_text)
            temp_file_path = temp_file.name

        # Create Discord File object
        file = discord.File(
            temp_file_path,
            filename=f'model_response_{message_id}.md'
        )
        # Schedule file deletion
        async def delete_temp_file():
            await asyncio.sleep(1)  # Wait a bit to ensure file is sent
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logging.error(f"Failed to delete temp file: {str(e)}")
        asyncio.create_task(delete_temp_file())
        return file

async def setup(bot):
    # Register the cog with its proper name
    try:
        cog = BaseCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[BaseCog] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[BaseCog] Failed to register cog: {str(e)}", exc_info=True)
        raise
