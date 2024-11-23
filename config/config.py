import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord bot token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Per-cog Discord tokens
CLAUDE3HAIKU_TOKEN = os.getenv('CLAUDE3HAIKU_TOKEN')
DEEPSEEK_TOKEN = os.getenv('DEEPSEEK_TOKEN')
GPT4O_TOKEN = os.getenv('GPT4O_TOKEN')
GROK_TOKEN = os.getenv('GROK_TOKEN')
HERMES_TOKEN = os.getenv('HERMES_TOKEN')
INFEROR_TOKEN = os.getenv('INFEROR_TOKEN')
LLAMAVISION_TOKEN = os.getenv('LLAMAVISION_TOKEN')
MAGNUM_TOKEN = os.getenv('MAGNUM_TOKEN')
NEMOTRON_TOKEN = os.getenv('NEMOTRON_TOKEN')
QWEN_TOKEN = os.getenv('QWEN_TOKEN')
ROCINANTE_TOKEN = os.getenv('ROCINANTE_TOKEN')
SONAR_TOKEN = os.getenv('SONAR_TOKEN')
SYDNEY_TOKEN = os.getenv('SYDNEY_TOKEN')
UNSLOP_TOKEN = os.getenv('UNSLOP_TOKEN')
WIZARD_TOKEN = os.getenv('WIZARD_TOKEN')

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

# OpenPipe API key
OPENPIPE_API_KEY = os.getenv('OPENPIPE_API_KEY')

# OpenPipe API URL (base URL only, chat/completions is added by the client)
OPENPIPE_API_URL = os.getenv('OPENPIPE_API_URL', 'https://api.openpipe.ai/api/v1')

# OpenAI API key (dummy)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'sk-dummy-openai-api-key')

# Helicone API key
HELICONE_API_KEY = os.getenv('HELICONE_API_KEY')

# Logging level
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Context windows (can be updated dynamically)
CONTEXT_WINDOWS = {}

# Default context window
DEFAULT_CONTEXT_WINDOW = 10

# Maximum context window
MAX_CONTEXT_WINDOW = 50

# Other configuration variables can be added here as needed
# Error Messages
ERROR_MESSAGES = {
    'credits_depleted': "⚠️ Credits depleted. Please contact the bot administrator.",
    'invalid_api_key': "🔑 Invalid API key. Please contact the bot administrator.",
    'rate_limit': "⏳ Rate limit exceeded. Please try again later.",
    'network_error': "🌐 Network error. Please try again later.",
    'unknown_error': "❌ An error occurred. Please try again later.",
    'reporting_error': "📝 Unable to log interaction, but response was successful."
}
# Keyword Blocklist
BLOCKED_KEYWORDS = [
    # Content warnings
    "nsfw",
    "porn",
    "hentai",
    "sex",
    "nude",
    "explicit",
    "adult",
    "xxx",
    "r18",
    "erotic",
    "lewd",
    "gore",
    "violence",
    "death",
    "suicide",
    "kill",
    "murder",
    "blood",
    "torture",
    "abuse",
    "rape",
    "drugs",
    "cocaine",
    "heroin",
    "meth",
    "illegal",
    "hack",
    "crack",
    "pirate",
    "torrent",
    "warez",
    "stolen",
    "leak",
    "exploit",
    
    # Specific blocked terms
    "pig42",
    "pig 42",
    "pig420377",
    "robespeeair",
    "robespeair",
    "robespear",
    "andwogynous",
    "androgynous",
    "shitpostew",
    "shitposter",
    "cutedeity",
    "anstarmus",
    "foss home lab lord",
]
