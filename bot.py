import discord
from discord.ext import commands, tasks
import logging
import os
import config
import importlib
import asyncio
import random
import aiohttp
import json
from datetime import datetime, timedelta
import re
import pytz
import traceback
from shared.api import api  # Import the API singleton

# Define BOT_DIR as the current working directory
BOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure logging
logging.basicConfig(
    level=config.LOG_LEVEL, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# Set up intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.typing = True
intents.dm_messages = True
intents.guilds = True
intents.members = True

class SplinterTreeBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_messages = set()
        self.api_client = api
        self.loaded_cogs = []
        self.message_history = {}
        self.last_used_cogs = {}
        self.start_time = None
        self.last_interaction = {
            'user': None,
            'time': None
        }
        self.cogs_loaded = False  # Flag to prevent multiple cog setups
        self.last_status_check = 0  # Track last status check time
        self.current_status = None  # Track current custom status
        self.tree.on_error = self.on_app_command_error  # Set up error handler for slash commands
        self._cleanup_tasks = []
        self.config = config  # Store config module for cogs to access

    async def close(self):
        """Cleanup when bot is shutting down"""
        logging.info("Bot is shutting down, cleaning up resources...")
        
        # Cancel all cleanup tasks
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Stop the status update task if it's running
        if update_status.is_running():
            update_status.cancel()

        # Unload all cogs
        for extension in list(self.extensions.keys()):
            try:
                await self.unload_extension(extension)
                logging.info(f"Unloaded extension: {extension}")
            except Exception as e:
                logging.error(f"Error unloading extension {extension}: {e}")

        # Close API client and cleanup resources
        try:
            await self.api_client.close()
            logging.info("Closed API client")
        except Exception as e:
            logging.error(f"Error closing API client: {e}")

        # Call parent's close method
        await super().close()
        logging.info("Bot shutdown complete")

    async def process_commands(self, message):
        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handle slash command errors"""
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏳ This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        elif isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            logging.error(f"Slash command error: {str(error)}")
            logging.error(traceback.format_exc())
            await interaction.response.send_message(
                "❌ An error occurred while executing the command.",
                ephemeral=True
            )

    def get_uptime_enabled(self):
        """Get uptime status toggle state"""
        try:
            with open('bot_config.json', 'r') as f:
                config_data = json.load(f)
                return config_data.get('uptime_enabled', True)
        except:
            return True

    async def check_status_file(self):
        """Check if there's a new status to set"""
        try:
            if not os.path.exists('bot_status.txt'):
                return
            
            # Check file modification time
            mod_time = os.path.getmtime('bot_status.txt')
            if mod_time <= self.last_status_check:
                return
            
            # Read and update status
            with open('bot_status.txt', 'r') as f:
                status = f.read().strip()
            
            if status:
                self.current_status = status
                await self.change_presence(activity=discord.Game(name=status))
                self.last_status_check = mod_time
                
                # Clear the file
                with open('bot_status.txt', 'w') as f:
                    f.write('')
                
        except Exception as e:
            logging.error(f"Error checking status file: {e}")

    async def setup_hook(self):
        """A coroutine to be called to setup the bot, by default this is blank."""
        # Sync commands with Discord
        try:
            await self.tree.sync()
            logging.info("Successfully synced slash commands")
        except Exception as e:
            logging.error(f"Failed to sync slash commands: {e}")

async def load_context_settings():
    """Load saved context window settings"""
    try:
        settings_file = os.path.join(BOT_DIR, 'context_windows.json')
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                config.CONTEXT_WINDOWS.update(settings)
                logging.info("Loaded context window settings")
    except Exception as e:
        logging.error(f"Error loading context settings: {str(e)}")

async def setup_cogs(bot: SplinterTreeBot):
    """Load all cogs"""
    if bot.cogs_loaded:
        logging.info("Cogs have already been loaded. Skipping setup.")
        return

    # Initialize API first
    try:
        await bot.api_client.setup()
        logging.info("API client initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize API client: {str(e)}")
        return

    bot.loaded_cogs = []  # Reset loaded cogs list

    # Load context settings
    await load_context_settings()

    # First load core cogs
    core_cogs = ['context_cog', 'management_cog', 'webhook_cog', 'router_cog']
    for cog in core_cogs:
        try:
            await bot.load_extension(f'cogs.{cog}')
            logging.info(f"Loaded core cog: {cog}")
        except Exception as e:
            logging.error(f"Failed to load core cog {cog}: {str(e)}")
            logging.error(traceback.format_exc())

    # Then load all model cogs
    cogs_dir = os.path.join(BOT_DIR, 'cogs')
    for filename in os.listdir(cogs_dir):
        if filename.endswith('_cog.py') and filename not in ['base_cog.py', 'help_cog.py', 'sorcerer_cog.py']:
            module_name = filename[:-3]
            try:
                await bot.load_extension(f'cogs.{module_name}')
                logging.debug(f"Attempting to load cog: {module_name}")
                
                # Dynamically derive the cog class name from the module name
                class_name = ''.join(word.capitalize() for word in module_name.split('_'))
                
                cog_instance = bot.get_cog(class_name)
                if cog_instance and hasattr(cog_instance, 'handle_message'):
                    bot.loaded_cogs.append(cog_instance)
                    logging.info(f"Loaded cog: {cog_instance.name}")
                
            except commands.errors.ExtensionAlreadyLoaded:
                logging.info(f"Extension 'cogs.{module_name}' is already loaded, skipping.")
            except Exception as e:
                logging.error(f"Failed to load cog {filename}: {str(e)}")
                logging.error(traceback.format_exc())

    # Finally load help cog after all other cogs are loaded
    try:
        await bot.load_extension('cogs.help_cog')
        logging.info("Loaded help cog")
        
        # Ensure help command is accessible
        help_cog = bot.get_cog('HelpCog')
        if help_cog:
            logging.info("Help cog loaded successfully")
        else:
            logging.error("Failed to find HelpCog after loading")
    except Exception as e:
        logging.error(f"Failed to load help cog: {str(e)}")
        logging.error(traceback.format_exc())

    # Sync slash commands after all cogs are loaded
    try:
        await bot.tree.sync()
        logging.info("Successfully synced slash commands after loading cogs")
    except Exception as e:
        logging.error(f"Failed to sync slash commands after loading cogs: {e}")

    logging.info(f"Total loaded cogs with handle_message: {len(bot.loaded_cogs)}")
    for cog in bot.loaded_cogs:
        logging.debug(f"Available cog: {cog.name} (Vision: {getattr(cog, 'supports_vision', False)})")
    logging.info(f"Loaded extensions: {list(bot.extensions.keys())}")

    bot.cogs_loaded = True  # Set the flag to indicate cogs have been loaded

# Initialize bot with a default command prefix
bot = SplinterTreeBot(command_prefix='!', intents=intents, help_command=None)

# File to persist processed messages
PROCESSED_MESSAGES_FILE = os.path.join(BOT_DIR, 'processed_messages.json')

def load_processed_messages():
    """Load processed messages from file"""
    if os.path.exists(PROCESSED_MESSAGES_FILE):
        try:
            with open(PROCESSED_MESSAGES_FILE, 'r') as f:
                bot.processed_messages = set(json.load(f))
            logging.info(f"Loaded {len(bot.processed_messages)} processed messages from file")
        except Exception as e:
            logging.error(f"Error loading processed messages: {str(e)}")

def save_processed_messages():
    """Save processed messages to file"""
    try:
        with open(PROCESSED_MESSAGES_FILE, 'w') as f:
            json.dump(list(bot.processed_messages), f)
        logging.info(f"Saved {len(bot.processed_messages)} processed messages to file")
    except Exception as e:
        logging.error(f"Error saving processed messages: {str(e)}")

@tasks.loop(seconds=30)
async def update_status():
    """Update bot status"""
    try:
        # Check for status updates from web UI
        await bot.check_status_file()
        
        # If no custom status and uptime is enabled, show uptime
        if not bot.current_status and bot.get_uptime_enabled():
            uptime = get_uptime()
            await bot.change_presence(activity=discord.Game(name=f"Up for {uptime}"))
        elif bot.current_status:
            # Ensure custom status stays set
            await bot.change_presence(activity=discord.Game(name=bot.current_status))
    except Exception as e:
        logging.error(f"Error updating status: {str(e)}")

async def setup_cogs_task():
    """Load all cogs"""
    await setup_cogs(bot)

@bot.event
async def on_ready():
    pst = pytz.timezone('US/Pacific')
    bot.start_time = datetime.now(pst)
    logging.info(f"Bot is ready! Logged in as {bot.user.name}")
    
    # Set initial "Booting..." status
    await bot.change_presence(activity=discord.Game(name="Booting..."))
    
    await setup_cogs_task()
    
    # Start the status update task
    if not update_status.is_running():
        update_status.start()

def get_uptime():
    """Get bot uptime as a formatted string"""
    if bot.start_time is None:
        return "Unknown"
    pst = pytz.timezone('US/Pacific')
    current_time = datetime.now(pst)
    uptime = current_time - bot.start_time.astimezone(pst)
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)

@bot.event
async def on_message(message):
    # Skip if message is from this bot
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # Update last interaction
    bot.last_interaction['user'] = message.author.display_name
    bot.last_interaction['time'] = datetime.now(pytz.timezone('US/Pacific'))

    # Get the router cog and handle the message
    router_cog = bot.get_cog('RouterCog')
    if router_cog:
        await router_cog.handle_message(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # Ignore command not found errors
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"⏳ This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.")
    else:
        logging.error(f"Command error: {str(error)}")
        logging.error(traceback.format_exc())
        await ctx.reply("❌ An error occurred while executing the command.")

# Run bot
if __name__ == "__main__":
    logging.debug("Starting bot...")
    load_processed_messages()  # Load processed messages on startup
    
    async def run_bot():
        try:
            async with bot:
                await bot.start(config.DISCORD_TOKEN)
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, initiating shutdown...")
            await bot.close()
        except Exception as e:
            logging.error(f"Bot crashed: {e}")
            logging.error(traceback.format_exc())
            await bot.close()
        finally:
            # Ensure everything is cleaned up
            if not bot.is_closed():
                await bot.close()

    # Run the bot with proper asyncio handling
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt during startup")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        logging.error(traceback.format_exc())
