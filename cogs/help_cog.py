import discord
from discord.ext import commands
import logging
import json
import sqlite3
import os
from datetime import datetime
from typing import Optional
import aiohttp
import asyncio
from config.webhook_config import load_webhooks, MAX_RETRIES, WEBHOOK_TIMEOUT, DEBUG_LOGGING
from config import CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW, MAX_CONTEXT_WINDOW
from bot import get_uptime  # Import the get_uptime function

class HelpCog(commands.Cog, name="Help"):
    """Help commands and channel management"""
    
    def __init__(self, bot):
        self.bot = bot
        # Remove default help command
        self.bot.remove_command('help')
        self.context_cog = bot.get_cog('ContextCog')
        self.webhooks = load_webhooks()
        self.session = aiohttp.ClientSession()
        self.dynamic_prompts_file = "dynamic_prompts.json"
        self.activated_channels_file = "activated_channels.json"
        self.activated_channels = self.load_activated_channels()
        logging.debug("[Help] Initialized")

    def load_activated_channels(self):
        """Load activated channels from JSON file"""
        try:
            if os.path.exists(self.activated_channels_file):
                with open(self.activated_channels_file, 'r') as f:
                    channels = json.load(f)
                    logging.info(f"[Help] Loaded activated channels: {channels}")
                    return channels
            logging.info("[Help] No activated channels file found, creating new one")
            return {}
        except Exception as e:
            logging.error(f"[Help] Error loading activated channels: {e}")
            return {}

    def save_activated_channels(self):
        """Save activated channels to JSON file"""
        try:
            with open(self.activated_channels_file, 'w') as f:
                json.dump(self.activated_channels, f, indent=4)
            logging.info(f"[Help] Saved activated channels: {self.activated_channels}")
        except Exception as e:
            logging.error(f"[Help] Error saving activated channels: {e}")

    def get_all_models(self):
        """Get all models and their details from registered cogs"""
        models = []
        vision_models = []

        for cog in self.bot.cogs.values():
            if hasattr(cog, 'name') and hasattr(cog, 'model') and cog.name not in ["Help", "Context"]:
                model_info = {
                    'name': cog.name,
                    'nickname': getattr(cog, 'nickname', cog.name),
                    'trigger_words': getattr(cog, 'trigger_words', []),
                    'supports_vision': getattr(cog, 'supports_vision', False),
                    'model': getattr(cog, 'model', 'Unknown'),
                    'provider': getattr(cog, 'provider', 'Unknown'),
                    'description': getattr(cog, 'description', '')
                }

                if model_info['supports_vision']:
                    vision_models.append(model_info)
                else:
                    models.append(model_info)

        return vision_models, models

    def format_model_list(self, vision_models, models):
        """Format the model list for display"""
        help_text = """**🤖 Available AI Models**\n\n"""

        # Add vision-capable models
        if vision_models:
            help_text += "**Vision-Capable Models:**\n"
            for model in vision_models:
                triggers = ", ".join(model['trigger_words'])
                help_text += f"• **{model['name']}** [{model['model']} via {model['provider']}]\n"
                help_text += f"  *Triggers:* {triggers}\n"
                help_text += f"  *Special:* Can analyze images and provide descriptions\n"
                if model['description']:
                    help_text += f"  *Description:* {model['description']}\n\n"
                else:
                    help_text += "\n"

        # Add language models
        if models:
            help_text += "**Large Language Models:**\n"
            for model in models:
                triggers = ", ".join(model['trigger_words'])
                help_text += f"• **{model['name']}** [{model['model']} via {model['provider']}]\n"
                help_text += f"  *Triggers:* {triggers}\n"
                if model['description']:
                    help_text += f"  *Description:* {model['description']}\n\n"
                else:
                    help_text += "\n"

        return help_text

    def format_simple_model_list(self, vision_models, models):
        """Format a simple model list with just names and models"""
        model_list = "**Available Models:**\n"

        # Add vision models with a 📷 indicator
        for model in vision_models:
            model_list += f"📷 {model['name']} - {model['model']}\n"

        # Add regular models
        for model in models:
            model_list += f"💬 {model['name']} - {model['model']}\n"

        return model_list

    @commands.command(name="help", aliases=["st_help"])
    async def help_command(self, ctx):
        """Send a comprehensive help message with all available features"""
        try:
            # Get dynamically loaded models
            vision_models, models = self.get_all_models()
            model_list = self.format_model_list(vision_models, models)

            # Add special features and tips
            help_message = f"""{model_list}
**📝 Special Features:**
• **Context Management** - Manages conversation history and shared context between models
• **Intelligent Message Routing** - Routes messages to appropriate models based on content
• **Emotion Analysis** - Provides emotion analysis and interaction logging
• **Dynamic System Prompts** - Customizable per-channel system prompts with variable support
• **Webhook Integration** - Send responses through configured Discord webhooks using `!hook`
• **Administrative Commands** - Manage bot status and channel configurations
• **Database Interactions** - Manages SQLite database interactions for context and logging
• **Error Handling and Logging** - Enhanced error reporting for better troubleshooting

**💡 Tips:**
1. Models will respond when you mention their trigger words (e.g., 'nemotron', 'gemini')
2. Each model has unique strengths - try different ones for different tasks
3. Use `!listmodels` to see a simple list of available models
4. Use `!list_agents` to get detailed information about each agent
5. For private responses, you can DM the bot directly
6. To activate the router in a channel, use `!router_activate` (Admin only)
7. Customize system prompts per channel using `!set_system_prompt` (Admin only)
8. Use `!getcontext` to view the current context window size
9. Manage conversation context with `!setcontext`, `!resetcontext`, and `!clearcontext` (Admin only)
10. Use `!hook` to send responses through Discord webhooks

**Available Commands:**
• `!help` - Show this help message
• `!listmodels` - Show all available models (simple list)
• `!list_agents` - Show all available agents with detailed info
• `!uptime` - Show how long the bot has been running
• `!set_system_prompt <agent> <prompt>` - Set a custom system prompt for an AI agent (Admin only)
• `!reset_system_prompt <agent>` - Reset an AI agent's system prompt to default (Admin only)
• `!setcontext <size>` - Set the number of previous messages to include in context (Admin only)
• `!getcontext` - View current context window size
• `!resetcontext` - Reset context window to default size (Admin only)
• `!clearcontext [hours]` - Clear conversation history, optionally specify hours (Admin only)
• `!activate` - Make the bot respond to every message in the current channel (Admin only)
• `!deactivate` - Deactivate the bot's response to every message in the current channel (Admin only)
• `!router_activate` - Activate the router to respond to all messages in the current channel (Admin only)
• `!router_deactivate` - Deactivate the router in the current channel (Admin only)
• `!hook <message>` - Send a response through configured Discord webhooks
• `!list_activated` - List all activated channels in the current server (Admin only)

**System Prompt Variables:**
When setting custom system prompts, you can use these variables:
• `{{MODEL_ID}}` - The AI model's name
• `{{USERNAME}}` - The user's Discord display name
• `{{DISCORD_USER_ID}}` - The user's Discord ID
• `{{TIME}}` - Current local time (PST)
• `{{TZ}}` - Local timezone (PST)
• `{{SERVER_NAME}}` - Current Discord server name
• `{{CHANNEL_NAME}}` - Current channel name

"""
            # Send the help message in chunks to avoid exceeding Discord's message length limit
            for msg in [help_message[i:i + 2000] for i in range(0, len(help_message), 2000)]:
                await ctx.send(msg)

            logging.info(f"[Help] Sent help message to user {ctx.author.name}")
        except Exception as e:
            logging.error(f"[Help] Error sending help message: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while fetching the help message. Please try again later.")

    @commands.command(name="listmodels", aliases=["st_listmodels"])
    async def list_models_command(self, ctx):
        """Send a simple list of all available models"""
        try:
            vision_models, models = self.get_all_models()
            model_list = self.format_simple_model_list(vision_models, models)
            await ctx.send(model_list)
            logging.info(f"[Help] Sent model list to user {ctx.author.name}")
        except Exception as e:
            logging.error(f"[Help] Error sending model list: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while fetching the model list. Please try again later.")

    @commands.command(name="list_agents", aliases=["st_list_agents"])
    async def list_agents_command(self, ctx):
        """Send a detailed list of all available agents and their configurations"""
        try:
            vision_models, models = self.get_all_models()
            embed = discord.Embed(title="🤖 Available Agents", color=discord.Color.blue())
            for model in vision_models + models:
                triggers = ", ".join(model['trigger_words'])
                description = f"**Model:** {model['model']} via {model['provider']}\n"
                description += f"**Triggers:** {triggers}\n"
                if model['supports_vision']:
                    description += "*Supports vision and can analyze images.*\n"
                if model['description']:
                    description += f"**Description:** {model['description']}\n"
                embed.add_field(name=model['name'], value=description, inline=False)
            await ctx.send(embed=embed)
            logging.info(f"[Help] Sent agent list to user {ctx.author.name}")
        except Exception as e:
            logging.error(f"[Help] Error sending agent list: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while fetching the agent list. Please try again later.")

    @commands.command(name='st_setcontext')
    @commands.has_permissions(manage_messages=True)
    async def st_set_context(self, ctx, size: int):
        """Set the number of previous messages to include in context"""
        try:
            # Validate size
            if size < 1 or size > MAX_CONTEXT_WINDOW:
                await ctx.reply(f"❌ Context size must be between 1 and {MAX_CONTEXT_WINDOW}")
                return

            # Update context window for this channel
            channel_id = str(ctx.channel.id)
            CONTEXT_WINDOWS[channel_id] = size

            # Update database
            try:
                with sqlite3.connect('databases/interaction_logs.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT OR REPLACE INTO context_windows 
                    (channel_id, window_size, last_modified) 
                    VALUES (?, ?, ?)
                    ''', (channel_id, size, datetime.now().isoformat()))
                    conn.commit()
            except Exception as e:
                logging.warning(f"Could not update context_windows table: {str(e)}")

            await ctx.reply(f"✅ Context window set to {size} messages for this channel")
        except Exception as e:
            logging.error(f"Failed to set context: {str(e)}")
            await ctx.reply("❌ Failed to set context window")

    @commands.command(name='st_resetcontext')
    @commands.has_permissions(manage_messages=True)
    async def st_reset_context(self, ctx):
        """Reset context window to default size"""
        try:
            channel_id = str(ctx.channel.id)

            # Remove channel-specific context setting
            if channel_id in CONTEXT_WINDOWS:
                del CONTEXT_WINDOWS[channel_id]

            # Update database
            try:
                with sqlite3.connect('databases/interaction_logs.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    DELETE FROM context_windows WHERE channel_id = ?
                    ''', (channel_id,))
                    conn.commit()
            except Exception as e:
                logging.warning(f"Could not update context_windows table: {str(e)}")

            await ctx.reply(f"🔄 Context window reset to default ({DEFAULT_CONTEXT_WINDOW} messages)")
        except Exception as e:
            logging.error(f"Failed to reset context: {str(e)}")
            await ctx.reply("❌ Failed to reset context window")

    @commands.command(name='hook')
    async def hook_command(self, ctx, *, content: str = None):
        """Send a message through configured webhooks"""
        if not content:
            await ctx.reply("❌ Please provide a message after !hook")
            return

        if DEBUG_LOGGING:
            logging.info(f"[WebhookCog] Processing hook command: {content}")

        # Create a copy of the message with the content
        message = discord.Message.__new__(discord.Message)
        message.__dict__.update(ctx.message.__dict__)
        message.content = content

        # Find an appropriate LLM cog to handle the message
        response = None
        used_cog = None

        # Try router cog first if available
        router_cog = self.bot.get_cog('RouterCog')
        if router_cog:
            try:
                # Let router handle the message
                await router_cog.handle_message(message)
                # Get the last message sent by the bot in this channel
                async for msg in ctx.channel.history(limit=10):
                    if msg.author == self.bot.user and msg.content.startswith('['):
                        response = msg.content
                        used_cog = router_cog
                        break
            except Exception as e:
                logging.error(f"[WebhookCog] Error using router: {str(e)}")

        # If router didn't work, try direct cog matching
        if not response:
            for cog in self.bot.cogs.values():
                if hasattr(cog, 'trigger_words') and hasattr(cog, 'handle_message'):
                    msg_content = content.lower()
                    if any(word in msg_content for word in cog.trigger_words):
                        try:
                            # Let the cog handle the message
                            await cog.handle_message(message)
                            # Get the last message sent by the bot in this channel
                            async for msg in ctx.channel.history(limit=10):
                                if msg.author == self.bot.user and msg.content.startswith('['):
                                    response = msg.content
                                    used_cog = cog
                                    break
                        except Exception as e:
                            logging.error(f"[WebhookCog] Error with cog {cog.__class__.__name__}: {str(e)}")

        if response:
            # Send to webhooks
            success = await self.broadcast_to_webhooks(response)
            
            if success:
                await ctx.message.add_reaction('✅')
            else:
                await ctx.message.add_reaction('❌')
                await ctx.reply("❌ Failed to send message to webhooks")
        else:
            await ctx.reply("❌ No LLM cog responded to the message")

    @commands.command(name='router_activate')
    @commands.has_permissions(manage_messages=True)
    async def router_activate(self, ctx):
        """Activate the router to respond to all messages in the current channel"""
        try:
            router_cog = self.bot.get_cog('RouterCog')
            if router_cog:
                channel_id = str(ctx.channel.id)
                router_cog.activate_channel(channel_id)
                await ctx.reply("✅ Router activated for this channel")
            else:
                await ctx.reply("❌ Router cog not found")
        except Exception as e:
            logging.error(f"[Help] Error activating router: {str(e)}")
            await ctx.reply("❌ Failed to activate router")

    @commands.command(name='router_deactivate')
    @commands.has_permissions(manage_messages=True)
    async def router_deactivate(self, ctx):
        """Deactivate the router in the current channel"""
        try:
            router_cog = self.bot.get_cog('RouterCog')
            if router_cog:
                channel_id = str(ctx.channel.id)
                router_cog.deactivate_channel(channel_id)
                await ctx.reply("✅ Router deactivated for this channel")
            else:
                await ctx.reply("❌ Router cog not found")
        except Exception as e:
            logging.error(f"[Help] Error deactivating router: {str(e)}")
            await ctx.reply("❌ Failed to deactivate router")

    @commands.command(name="channel_activate", aliases=["activate", "st_activate"])
    @commands.has_permissions(manage_messages=True)
    async def activate_channel(self, ctx):
        """Activate the bot to respond to every message in the current channel"""
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else "dm"
            channel_id = str(ctx.channel.id)

            logging.info(f"[Help] Activating channel {channel_id} in guild {guild_id}")

            # Initialize guild dict if needed
            if guild_id not in self.activated_channels:
                self.activated_channels[guild_id] = {}

            # Add the channel
            self.activated_channels[guild_id][channel_id] = True
            self.save_activated_channels()

            # Reload activated channels in RouterCog
            router_cog = self.bot.get_cog('RouterCog')
            if router_cog:
                router_cog.activated_channels = self.activated_channels
                logging.info(f"[Help] Updated RouterCog activated channels: {router_cog.activated_channels}")

            await ctx.reply("✅ Bot will now respond to every message in this channel.")
        except Exception as e:
            logging.error(f"[Help] Error activating channel: {e}")
            await ctx.reply("❌ Failed to activate channel. Please try again.")

    @commands.command(name="channel_deactivate", aliases=["deactivate", "st_deactivate"])
    @commands.has_permissions(manage_messages=True)
    async def channel_deactivate(self, ctx):
        """Deactivate the bot's response to every message in the current channel"""
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else "dm"
            channel_id = str(ctx.channel.id)

            logging.info(f"[Help] Deactivating channel {channel_id} in guild {guild_id}")

            # Remove the channel if it exists
            if (guild_id in self.activated_channels and 
                channel_id in self.activated_channels[guild_id]):
                del self.activated_channels[guild_id][channel_id]
                
                # Clean up empty guild dict
                if not self.activated_channels[guild_id]:
                    del self.activated_channels[guild_id]
                
                self.save_activated_channels()

                # Reload activated channels in RouterCog
                router_cog = self.bot.get_cog('RouterCog')
                if router_cog:
                    router_cog.activated_channels = self.activated_channels
                    logging.info(f"[Help] Updated RouterCog activated channels: {router_cog.activated_channels}")

                await ctx.reply("✅ Bot will no longer respond to every message in this channel.")
            else:
                await ctx.reply("❌ This channel was not previously activated.")
        except Exception as e:
            logging.error(f"[Help] Error deactivating channel: {e}")
            await ctx.reply("❌ Failed to deactivate channel. Please try again.")

    @commands.command(name="list_activated", aliases=["st_list_activated"])
    @commands.has_permissions(manage_messages=True)
    async def list_activated_channels(self, ctx):
        """List all activated channels"""
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else "dm"
            
            if guild_id in self.activated_channels and self.activated_channels[guild_id]:
                activated_channels = list(self.activated_channels[guild_id].keys())
                channel_mentions = [f"<#{channel_id}>" for channel_id in activated_channels]
                
                await ctx.reply("Activated channels:\n" + "\n".join(channel_mentions))
            else:
                await ctx.reply("No channels are currently activated in this server.")
        except Exception as e:
            logging.error(f"[Help] Error listing activated channels: {e}")
            await ctx.reply("❌ Failed to list activated channels. Please try again.")

    @commands.command(name="set_system_prompt", aliases=["st_set_system_prompt"])
    @commands.has_permissions(manage_messages=True)
    async def set_system_prompt(self, ctx, agent: str, *, prompt: str):
        """Set a custom system prompt for an AI agent in this channel"""
        try:
            # Load existing prompts
            if os.path.exists(self.dynamic_prompts_file):
                with open(self.dynamic_prompts_file, "r") as f:
                    dynamic_prompts = json.load(f)
            else:
                dynamic_prompts = {}

            # Get guild and channel IDs
            guild_id = str(ctx.guild.id) if ctx.guild else None
            channel_id = str(ctx.channel.id)

            # Initialize guild dict if needed
            if guild_id and guild_id not in dynamic_prompts:
                dynamic_prompts[guild_id] = {}

            # Set the prompt
            if guild_id:
                if channel_id not in dynamic_prompts[guild_id]:
                    dynamic_prompts[guild_id][channel_id] = {}
                dynamic_prompts[guild_id][channel_id][agent] = prompt
            else:
                if channel_id not in dynamic_prompts:
                    dynamic_prompts[channel_id] = {}
                dynamic_prompts[channel_id][agent] = prompt

            # Save updated prompts
            with open(self.dynamic_prompts_file, "w") as f:
                json.dump(dynamic_prompts, f, indent=4)

            await ctx.reply(f"✅ System prompt updated for {agent} in this channel.")

        except Exception as e:
            logging.error(f"Error setting system prompt: {str(e)}")
            await ctx.reply("❌ Failed to set system prompt. Please try again.")

    @commands.command(name="reset_system_prompt", aliases=["st_reset_system_prompt"])
    @commands.has_permissions(manage_messages=True)
    async def reset_system_prompt(self, ctx, agent: str):
        """Reset the system prompt for an AI agent to its default in this channel"""
        try:
            if not os.path.exists(self.dynamic_prompts_file):
                await ctx.reply("No custom prompts found.")
                return

            with open(self.dynamic_prompts_file, "r") as f:
                dynamic_prompts = json.load(f)

            guild_id = str(ctx.guild.id) if ctx.guild else None
            channel_id = str(ctx.channel.id)

            # Remove prompt if it exists
            if guild_id and guild_id in dynamic_prompts:
                if channel_id in dynamic_prompts[guild_id]:
                    if agent in dynamic_prompts[guild_id][channel_id]:
                        del dynamic_prompts[guild_id][channel_id][agent]
                    if not dynamic_prompts[guild_id][channel_id]:
                        del dynamic_prompts[guild_id][channel_id]
                if not dynamic_prompts[guild_id]:
                    del dynamic_prompts[guild_id]
            elif channel_id in dynamic_prompts:
                if agent in dynamic_prompts[channel_id]:
                    del dynamic_prompts[channel_id][agent]
                if not dynamic_prompts[channel_id]:
                    del dynamic_prompts[channel_id]

            # Save updated prompts
            with open(self.dynamic_prompts_file, "w") as f:
                json.dump(dynamic_prompts, f, indent=4)

            await ctx.reply(f"✅ System prompt reset to default for {agent} in this channel.")

        except Exception as e:
            logging.error(f"Error resetting system prompt: {str(e)}")
            await ctx.reply("❌ Failed to reset system prompt. Please try again.")

    @commands.command(name='uptime')
    async def uptime_command(self, ctx):
        """Show how long the bot has been running"""
        uptime = get_uptime()
        await ctx.reply(f"🕒 Bot has been running for {uptime}")

    async def send_to_webhook(self, webhook_url: str, content: str, retries: int = 0) -> bool:
        """
        Send content to a Discord webhook
        Returns True if successful, False otherwise
        """
        if retries >= MAX_RETRIES:
            logging.error(f"[Help] Max retries reached for webhook")
            return False

        try:
            async with self.session.post(
                webhook_url,
                json={"content": content},
                timeout=WEBHOOK_TIMEOUT
            ) as response:
                if response.status == 429:  # Rate limited
                    retry_after = float(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await self.send_to_webhook(webhook_url, content, retries + 1)
                
                return 200 <= response.status < 300

        except asyncio.TimeoutError:
            logging.warning(f"[Help] Webhook request timed out, retrying...")
            return await self.send_to_webhook(webhook_url, content, retries + 1)
        except Exception as e:
            logging.error(f"[Help] Error sending to webhook: {str(e)}")
            return False

    async def broadcast_to_webhooks(self, content: str) -> bool:
        """
        Broadcast content to all configured webhooks
        Returns True if at least one webhook succeeded
        """
        if not self.webhooks:
            if DEBUG_LOGGING:
                logging.warning("[Help] No webhooks configured")
            return False

        success = False
        for webhook_url in self.webhooks:
            result = await self.send_to_webhook(webhook_url, content)
            success = success or result

        return success

async def setup(bot):
    try:
        # Remove default help command before adding our custom help command
        bot.remove_command('help')
        cog = HelpCog(bot)
        await bot.add_cog(cog)
        logging.info(f"[Help] Registered cog with qualified_name: {cog.qualified_name}")
        return cog
    except Exception as e:
        logging.error(f"[Help] Failed to register cog: {e}", exc_info=True)
        raise
