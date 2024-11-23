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
from bot import get_uptime

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
        self.prompts_file = "prompts/consolidated_prompts.json"
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

    def _save_system_prompts(self, prompts):
        """Save system prompts to file"""
        try:
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump({'system_prompts': prompts}, f, indent=2)
            logging.info("[Help] Saved system prompts")
        except Exception as e:
            logging.error(f"[Help] Error saving system prompts: {str(e)}")
            raise

    def _load_system_prompts(self):
        """Load system prompts from file"""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('system_prompts', {})
            return {}
        except Exception as e:
            logging.error(f"[Help] Error loading system prompts: {str(e)}")
            return {}

    @commands.hybrid_command(name="set_system_prompt", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        agent="The AI agent to set the prompt for",
        prompt="The new system prompt to use"
    )
    async def set_system_prompt(self, ctx, agent: str, *, prompt: str):
        """Set a custom system prompt for an AI agent. Use /set_system_prompt <agent> <prompt> or !set_system_prompt <agent> <prompt>"""
        try:
            # Load current prompts
            prompts = self._load_system_prompts()
            
            # Find the cog
            cog = None
            for c in self.bot.cogs.values():
                if hasattr(c, 'name') and c.name.lower() == agent.lower():
                    cog = c
                    break
            
            if not cog:
                await ctx.send(f"❌ Agent '{agent}' not found")
                return
            
            # Update the prompt
            prompts[agent.lower()] = prompt
            
            # Save prompts
            self._save_system_prompts(prompts)
            
            # Update the cog's prompt
            cog.raw_prompt = prompt
            
            await ctx.send(f"✅ System prompt updated for {agent}")
            
        except Exception as e:
            logging.error(f"[Help] Error setting system prompt: {str(e)}")
            await ctx.send("❌ Error setting system prompt")

    @commands.hybrid_command(name="reset_system_prompt", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(agent="The AI agent to reset the prompt for")
    async def reset_system_prompt(self, ctx, agent: str):
        """Reset an AI agent's system prompt to default. Use /reset_system_prompt <agent> or !reset_system_prompt <agent>"""
        try:
            # Load current prompts
            prompts = self._load_system_prompts()
            
            # Find the cog
            cog = None
            for c in self.bot.cogs.values():
                if hasattr(c, 'name') and c.name.lower() == agent.lower():
                    cog = c
                    break
            
            if not cog:
                await ctx.send(f"❌ Agent '{agent}' not found")
                return
            
            # Remove the custom prompt if it exists
            if agent.lower() in prompts:
                del prompts[agent.lower()]
                
            # Save prompts
            self._save_system_prompts(prompts)
            
            # Reset the cog's prompt to default
            cog.raw_prompt = cog.default_prompt
            
            await ctx.send(f"✅ System prompt reset to default for {agent}")
            
        except Exception as e:
            logging.error(f"[Help] Error resetting system prompt: {str(e)}")
            await ctx.send("❌ Error resetting system prompt")

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

    @commands.hybrid_command(name="help", with_app_command=True)
    async def help_command(self, ctx):
        """Show all available commands and features. Use /help or !help"""
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
• **Webhook Integration** - Send responses through configured Discord webhooks using `/hook` or `!hook`
• **Administrative Commands** - Manage bot status and channel configurations
• **Database Interactions** - Manages SQLite database interactions for context and logging
• **Error Handling and Logging** - Enhanced error reporting for better troubleshooting

**💡 Tips:**
1. Models will respond when you mention their trigger words (e.g., 'nemotron', 'gemini')
2. Each model has unique strengths - try different ones for different tasks
3. Use `/listmodels` or `!listmodels` to see a simple list of available models
4. Use `/list_agents` or `!list_agents` to get detailed information about each agent
5. For private responses, you can DM the bot directly
6. To activate the bot in a channel, use `/activate` or `!activate` (Admin only)
7. Customize system prompts per channel using `/set_system_prompt` or `!set_system_prompt` (Admin only)
8. Use `/getcontext` or `!getcontext` to view the current context window size
9. Manage conversation context with `/setcontext`, `/resetcontext`, and `/clearcontext` (Admin only)
10. Use `/hook` or `!hook` to send responses through Discord webhooks

**Available Commands:**
All commands support both slash (/) and prefix (!) formats:
• `/help` - Show this help message
• `/listmodels` - Show all available models (simple list)
• `/list_agents` - Show all available agents with detailed info
• `/uptime` - Show how long the bot has been running
• `/set_system_prompt <agent> <prompt>` - Set a custom system prompt for an AI agent (Admin only)
• `/reset_system_prompt <agent>` - Reset an AI agent's system prompt to default (Admin only)
• `/setcontext <size>` - Set the number of previous messages to include in context (Admin only)
• `/getcontext` - View current context window size
• `/resetcontext` - Reset context window to default size (Admin only)
• `/clearcontext [hours]` - Clear conversation history, optionally specify hours (Admin only)
• `/activate` - Make the bot respond to every message in the current channel (Admin only)
• `/deactivate` - Deactivate the bot's response to every message in the current channel (Admin only)
• `/hook <message>` - Send a response through configured Discord webhooks
• `/list_activated` - List all activated channels in the current server (Admin only)

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

    @commands.hybrid_command(name="listmodels", with_app_command=True)
    async def list_models_command(self, ctx):
        """Show a simple list of all available models. Use /listmodels or !listmodels"""
        try:
            vision_models, models = self.get_all_models()
            model_list = self.format_simple_model_list(vision_models, models)
            await ctx.send(model_list)
            logging.info(f"[Help] Sent model list to user {ctx.author.name}")
        except Exception as e:
            logging.error(f"[Help] Error sending model list: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while fetching the model list. Please try again later.")

    @commands.hybrid_command(name="list_agents", with_app_command=True)
    async def list_agents_command(self, ctx):
        """Show detailed information about all available agents. Use /list_agents or !list_agents"""
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

    @commands.hybrid_command(name="uptime", with_app_command=True)
    async def uptime_command(self, ctx):
        """Show how long the bot has been running. Use /uptime or !uptime"""
        try:
            uptime = get_uptime()
            await ctx.send(f"🕒 Bot has been running for: {uptime}")
            logging.info(f"[Help] Sent uptime to user {ctx.author.name}")
        except Exception as e:
            logging.error(f"[Help] Error sending uptime: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while fetching the uptime. Please try again later.")

    @commands.hybrid_command(name='hook')
    @discord.app_commands.describe(content="Message to send through webhooks")
    async def hook_command(self, ctx, *, content: str = None):
        """Send a message through configured webhooks. Use /hook or !hook"""
        if not content:
            await ctx.reply("❌ Please provide a message after /hook or !hook")
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

    @commands.hybrid_command(name="list_activated")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def list_activated_channels(self, ctx):
        """List all activated channels in the current server. Use /list_activated or !list_activated"""
        try:
            router_cog = self.bot.get_cog('RouterCog')
            if not router_cog:
                await ctx.reply("❌ Router cog not found")
                return

            guild_id = str(ctx.guild.id)
            
            if guild_id in router_cog.activated_channels and router_cog.activated_channels[guild_id]:
                activated_channels = list(router_cog.activated_channels[guild_id].keys())
                channel_mentions = [f"<#{channel_id}>" for channel_id in activated_channels]
                
                await ctx.reply("Activated channels:\n" + "\n".join(channel_mentions))
            else:
                await ctx.reply("No channels are currently activated in this server.")
        except Exception as e:
            logging.error(f"[Help] Error listing activated channels: {e}")
            await ctx.reply("❌ Failed to list activated channels. Please try again.")

    async def cog_load(self):
        """Called when the cog is loaded. Sync slash commands."""
        try:
            await self.bot.tree.sync()
            logging.info("[Help] Slash commands synced successfully")
        except Exception as e:
            logging.error(f"[Help] Failed to sync slash commands: {e}")

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
