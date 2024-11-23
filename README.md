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
- **GPT4OCog**:
  - **Model**: `openpipe:openrouter/openai/gpt-4o-2024-11-20`
  - **Provider**: `openpipe`
  - **Trigger**: `'gpt4o', '4o', 'openai'`
  - **Vision Support**: **No**
  - **Temperature**: Configurable via `temperatures.json`
  - **Strengths**:
    - Specialized model for focused functionality.
    - Temperature control for creativity and randomness.
    - Contextual understanding through context cog integration.
    - API integration with `openrouter`.
    - Comprehensive error handling.
  - **Weaknesses**:
    - Dependency on external API.
    - Limited flexibility.
    - Potential performance issues.
    - Configuration requirements.

- **GrokCog**:
  - **Model**: `openpipe:openrouter/x-ai/grok-beta`
  - **Provider**: `openpipe`
  - **Trigger**: `'grok', 'xAI'`
  - **Vision Support**: **No**
  - **Temperature**: Configurable via `temperatures.json`
  - **Strengths**:
    - Specialized model for focused functionality.
    - Temperature control for creativity and randomness.
    - Contextual understanding through context cog integration.
    - API integration with `openrouter`.
    - Comprehensive error handling.
  - **Weaknesses**:
    - Dependency on external API.
    - Limited flexibility.
    - Potential performance issues.
    - Configuration requirements.

- **HelpCog**:
  - **Strengths**:
    - Comprehensive help commands including model lists and descriptions.
    - Model list management commands (`/listmodels`, `/list_agents`).
    - System prompt management commands (`/set_system_prompt`, `/reset_system_prompt`).
    - Webhook integration command (`/hook`).
    - Error handling for various commands.
    - Slash command support.
  - **Weaknesses**:
    - Dependency on other cogs like RouterCog for some functionalities.
    - Complexity in error handling which might add complexity to the codebase if not managed properly.
    - Limited flexibility in webhook handling which is specific to sending messages through configured webhooks.

- **ManagementCog**:
  - **Strengths**:
    - Opt-out feature allowing users to opt out of all bot interactions via `optout`.
    - Database interaction for managing banned users securely using SQLite.
    - Comprehensive error handling ensuring any issues are logged and managed properly.
    - API integration with `openrouter`.
    - Contextual understanding through context cog integration.
  - **Weaknesses**:
    - Dependency on external API which could be a weakness if it experiences downtime or changes its interface.
    - Limited flexibility as it is highly specialized for management tasks.
    - Potential performance issues due to database operations.
    - Configuration requirements for specific files like `temperatures.json`.

- **WebhookCog**:
  - **Strengths**:
    - Webhook integration for sending LLM responses through Discord webhooks.
    - Comprehensive error handling including retries for rate limits and timeouts.
    - Scalability in handling multiple webhooks.
    - Customization options for webhooks with unique names and avatars.
    - Automation of sending messages through webhooks.
  - **Weaknesses**:
    - Rate limitations which may still fail if exceeded despite retries.
    - Complexity in error handling mechanism.
    - Configuration requirements for specific settings like `MAX_RETRIES`, `WEBHOOK_TIMEOUT`.

- **InferorCog**:
  - **Model**: `openpipe:infermatic/Infermatic-MN-12B-Inferor-v0.0`
  - **Provider**: `openpipe`
  - **Trigger**: `'inferor'`
  - **Vision Support**: **No**
  - **Temperature**: Configurable via `temperatures.json`
  - **Strengths**:
    - Specialized model for focused functionality.
    - Temperature control for creativity and randomness.
    - Contextual understanding through context cog integration.
    - API integration with `openrouter`.
    - Comprehensive error handling.
  - **Weaknesses**:
    - Dependency on external API.
    - Limited flexibility.
    - Potential performance issues.
    - Configuration requirements.

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

**Note**: Commands are prefixed with `` and may require administrative permissions.

- **`help`**: Show help message with a list of features and commands.
- **`listmodels`**: Show all available models (simple list).
- **`list_agents`**: Show all available agents with detailed info.
- **`uptime`**: Show how long the bot has been running.
- **`set_system_prompt <agent> <prompt>`**: Set a custom system prompt for an AI agent (Admin only).
- **`reset_system_prompt <agent>`**: Reset an AI agent's system prompt to default (Admin only).
- **`setcontext <size>`**: Set the number of previous messages to include in context (Admin only).
- **`getcontext`**: View current context window size.
- **`resetcontext`**: Reset context window to default size (Admin only).
- **`clearcontext [hours]`**: Clear conversation history, optionally specify hours (Admin only).
- **`router_activate`**: Activate the router to respond to all messages in the current channel (Admin only).
- **`router_deactivate`**: Deactivate the router in the current channel (Admin only).
- **`hook <message>`**: Send a response through configured Discord webhooks.
- **`channel_activate`**: Make the bot respond to every message in the current channel (Admin only).
- **`channel_deactivate`**: Deactivate the bot's response to every message in the current channel (Admin only).
- **`list_activated`**: List all activated channels in the current server (Admin only).

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
