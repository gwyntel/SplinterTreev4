# 🌳 SplinterTree v4

A powerful Discord bot that provides access to multiple AI language models with advanced features like shared conversation context, image processing, dynamic prompting, and intelligent message routing.

## ✨ Features

### Core Features

- **Multi-Model Support**: Access a variety of AI models through OpenRouter and OpenPipe, including specialized models for different tasks.
- **Intelligent Message Routing**: Routes messages to appropriate models based on content with the **RouterCog**, handling DMs and channel activation while preventing routing loops.
- **Context Management**: Manages conversation history using **ContextCog**, with per-channel message history and configurable context window sizes.
- **Shared Context Database**: SQLite-based persistent conversation history shared between all models, enabling cross-model context.
- **Dynamic System Prompts**: Customizable per-channel system prompts with variable support for personalized interactions.
- **Emotion Analysis**: Provides emotion analysis and interaction logging for more engaging responses.
- **Response Reroll**: Button to generate alternative responses if needed.
- **Universal Image Processing**: Automatic image description and analysis for all models, even if they don't have native vision support.
- **File Handling**: Support for text files and images, with automatic content extraction.
- **Administrative Commands**: Manage bot status and channel configurations using **ManagementCog**.
- **Enhanced Error Handling and Logging**: Improved error reporting for better troubleshooting and maintenance.
- **Webhook Integration**: Send responses through configured Discord webhooks using the **WebhookCog**.
- **Agent Cloning**: Create custom variants of existing agents with unique system prompts.
- **PST Timezone Preference**: All time-related operations use Pacific Standard Time (PST) by default.
- **User ID Resolution**: Automatically resolves Discord user IDs to usernames in messages.
- **Attachment-Only Processing**: Handles messages containing only attachments (images, text files) without additional text.
- **Automatic Database Initialization**: Schema is automatically applied on bot startup.
- **OpenPipe Request Reporting**: Automatic logging for analysis and potential model improvement.
- **Message ID Tracking**: Prevents duplicate messages by tracking processed message IDs.
- **Router Mode**: Ability to make the Router respond to all messages in a channel.
- **Per-Channel Activation**: Activate or deactivate bot responses in specific channels.

### Specialized Model Cogs

- **MixtralCog**: General-purpose model with configurable temperature settings.
- **GeminiCog**: Vision-capable model specialized in image analysis.
- **SonarCog**: Specialized in current events and real-time information processing.
- **NemotronCog**: Technical and code-focused model with complex system design capabilities.
- **NoromaidCog**: Roleplay and narrative-focused model handling complex scenes.
- **UnslopNemoCog**: Handles medium-length interactions with group scenes and dialogue.
- **LiquidCog**: Provides quick actions and short-form content responses.
- **HermesCog**: Focused on mental health and crisis support, handling sensitive topics with high priority.

## 🛠️ Setup

### Prerequisites

- **Python 3.10+**
- **Discord Bot Token**: For bot authentication.
- **OpenRouter API Key**: For model routing capabilities.
- **OpenPipe API Key and URL**: For model access and interaction logging.
- **OpenAI API Key**: For additional services.
- **SQLite3**: For database interactions.

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/SplinterTreev4.git
   cd SplinterTreev4
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:

   - Copy `.env.example` to `.env`
   - Add your API keys and configuration variables as per the **Environment Variables** section.

4. **Initialize the database**:

   ```bash
   python initialize_interaction_logs_db.py
   ```

5. **Run the bot**:

   ```bash
   python bot.py
   ```

### Heroku Deployment

1. **Create a new Heroku app**.
2. **Set your environment variables** in Heroku settings as per the **Environment Variables** section.
3. **Deploy using Git or GitHub integration**.
4. **Scale dynos**:

   ```bash
   heroku ps:scale worker=1
   ```

## ⚙️ Configuration

### Environment Variables

```bash
# Discord Bot Configuration
DISCORD_TOKEN=           # Discord bot authentication token
                        # Format: MTxxxxxxxxxx.xxxxxx.xxx-xxxxxxxxxxxxxxxxxxxxx

# OpenPipe Configuration
OPENPIPE_API_KEY=       # OpenPipe API key for model access
                        # Format: opk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENPIPE_API_URL=       # OpenPipe API endpoint
                        # Default: https://api.openpipe.ai/api/v1

# OpenRouter Configuration
OPENROUTER_API_KEY=     # OpenRouter API key for model routing
                        # Format: sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI Configuration
OPENAI_API_KEY=         # OpenAI API key for additional services
                        # Format: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Debug Configuration
DEBUG=false             # Enable/disable debug mode
LOG_LEVEL=INFO          # Logging level (INFO, DEBUG, ERROR, etc.)
```

### Configuration Files

- **`temperatures.json`**: Model temperature settings (default: `0.7` if not specified).
- **`dynamic_prompts.json`**: Custom system prompts per channel to override default prompts.
- **`bot_config.json`**: Bot configuration settings for status display and feature toggles.
- **`databases/schema.sql`**: SQLite database schema for context and interaction logging.
- **`activated_channels.json`**: Tracks channels where the bot is activated.

## 🧩 Cog Architecture

### Core Cogs

1. **BaseCog** (`base_cog.py`)
   - Parent class for all model cogs.
   - Handles message processing and context management.
   - Implements reroll functionality.
   - Manages bot profile updates and typing indicators.
   - Provides emotion analysis and interaction logging.

2. **RouterCog** (`router_cog.py`)
   - Intelligent message routing system.
   - Routes messages to appropriate models based on content.
   - Handles DMs and channel activation.
   - Prevents routing loops.
   - Model: `mistralai/ministral-3b`
   - Provider: `openrouter`

3. **ContextCog** (`context_cog.py`)
   - Manages conversation history.
   - Handles context windows and summaries.
   - Maintains shared context between models.
   - Manages SQLite database interactions.

4. **HelpCog** (`help_cog.py`)
   - Provides command documentation.
   - Lists available models and features.
   - Manages system prompts.
   - Handles webhook integrations.

### Model Cogs

1. **MixtralCog** (`mixtral_cog.py`)
   - Model: `mistralai/pixtral-12b`
   - Provider: `openrouter`
   - Trigger: `'mixtral'`
   - Vision support: **No**
   - Temperature: Configurable via `temperatures.json`

2. **GeminiCog** (`gemini_cog.py`)
   - Vision-capable model.
   - Specialized in image analysis.
   - Trigger: `'gemini'`
   - Vision support: **Yes**

3. **SonarCog** (`sonar_cog.py`)
   - Specialized in current events and updates.
   - Real-time information processing.
   - Trigger: `'sonar'`

4. **NemotronCog** (`nemotron_cog.py`)
   - Technical and code-focused model.
   - Complex system design capabilities.
   - Trigger: `'nemotron'`

5. **NoromaidCog** (`noromaid_cog.py`)
   - Roleplay and narrative focused.
   - Complex scene handling.
   - Trigger: `'noromaid'`

6. **UnslopNemoCog** (`unslopnemo_cog.py`)
   - Medium-length interactions.
   - Group scenes and dialogue.
   - Trigger: `'unslopnemo'`

7. **LiquidCog** (`liquid_cog.py`)
   - Quick actions and responses.
   - Short-form content.
   - Trigger: `'liquid'`

8. **HermesCog** (`hermes_cog.py`)
   - Mental health and crisis support.
   - High priority for sensitive topics.
   - Trigger: `'hermes'`

### Management Cogs

1. **ManagementCog** (`management_cog.py`)
   - Administrative commands.
   - Bot status management.
   - Channel configuration.

2. **WebhookCog** (`webhook_cog.py`)
   - Handles Discord webhook integrations.
   - Response broadcasting.
   - Webhook configuration management.

## 🔧 Commands

**Note**: Commands are prefixed with `!` and may require administrative permissions.

- **`!help`**: Show help message with a list of features and commands.
- **`!listmodels`**: Show all available models (simple list).
- **`!list_agents`**: Show all available agents with detailed info.
- **`!uptime`**: Show how long the bot has been running.
- **`!set_system_prompt <agent> <prompt>`**: Set a custom system prompt for an AI agent (Admin only).
- **`!reset_system_prompt <agent>`**: Reset an AI agent's system prompt to default (Admin only).
- **`!setcontext <size>`**: Set the number of previous messages to include in context (Admin only).
- **`!getcontext`**: View current context window size.
- **`!resetcontext`**: Reset context window to default size (Admin only).
- **`!clearcontext [hours]`**: Clear conversation history, optionally specify hours (Admin only).
- **`!router_activate`**: Activate the router to respond to all messages in the current channel (Admin only).
- **`!router_deactivate`**: Deactivate the router in the current channel (Admin only).
- **`!hook <message>`**: Send a response through configured Discord webhooks.
- **`!channel_activate`**: Make the bot respond to every message in the current channel (Admin only).
- **`!channel_deactivate`**: Deactivate the bot's response to every message in the current channel (Admin only).
- **`!list_activated`**: List all activated channels in the current server (Admin only).

## 📚 System Prompt Variables

When setting custom system prompts, you can use these variables:

- `{{MODEL_ID}}`: The AI model's name.
- `{{USERNAME}}`: The user's Discord display name.
- `{{DISCORD_USER_ID}}`: The user's Discord ID.
- `{{TIME}}`: Current local time (PST).
- `{{TZ}}`: Local timezone (PST).
- `{{SERVER_NAME}}`: Current Discord server name.
- `{{CHANNEL_NAME}}`: Current channel name.

## ⚠️ Critical Reminders

1. **Never modify**:

   - Model strings in cogs.
   - Base error handling.
   - Core routing logic.
   - Database schema without migration.

2. **Always update**:

   - `README.md` for new features.
   - Help command documentation.
   - Test coverage.
   - Error logging.

3. **After deployment**:

   - Monitor Heroku logs with `heroku logs --tail`.
   - Check `bot_status.txt`.
   - Verify API connections.
   - Monitor error rates.

## 📝 Key Files

1. **`temperatures.json`**
   - Model temperature settings.
   - Default: `0.7` if not specified.

2. **`dynamic_prompts.json`**
   - Custom system prompts per channel.
   - Override default prompts.

3. **`bot_config.json`**
   - Bot configuration settings.
   - Status display settings.
   - Feature toggles.

4. **`databases/schema.sql`**
   - SQLite database schema.
   - Context and interaction logging tables.

5. **`activated_channels.json`**
   - Tracks channels where the bot is activated.

---
