# 🌳 SplinterTree v4

A powerful Discord bot that provides access to multiple AI language models with advanced features like shared conversation context, image processing, dynamic prompting, and intelligent message routing.

## ✨ Features

### Core Features

- **Multi-Model Support**: Access a variety of AI models through OpenRouter and OpenPipe, including specialized models for different tasks.
- **Intelligent Message Routing**: Routes messages to appropriate models based on content with the **RouterCog**, handling DMs and channel activation while preventing routing loops.  The routing logic is detailed in the section below.
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

This section details the individual cogs responsible for interacting with specific AI models. Each cog description includes information about the model used, its provider, triggers, vision support, temperature settings, strengths, and weaknesses.

- **MixtralCog**: General-purpose model with configurable temperature settings.
- **GeminiCog**: Vision-capable model specialized in image analysis.
- **SonarCog**: Specialized in current events and real-time information processing. See above for details.
- **NemotronCog**: Technical and code-focused model with complex system design capabilities. See above for details.
- **NoromaidCog**: Roleplay and narrative-focused model handling complex scenes.
- **UnslopNemoCog**: Handles medium-length interactions with group scenes and dialogue.
- **LiquidCog**: Provides quick actions and short-form content responses.
- **HermesCog**: Focused on mental health and crisis support, handling sensitive topics with high priority. See above for details.
- **GPT4OCog**:  Details about GPT-4O model, provider, triggers, vision support, temperature, strengths, and weaknesses. See above for details.
- **GrokCog**: Details about Grok model, provider, triggers, vision support, temperature, strengths, and weaknesses. See above for details.
- **HelpCog**: Details about HelpCog functionality, strengths, and weaknesses. See above for details.
- **ManagementCog**: Details about ManagementCog functionality, strengths, and weaknesses. See above for details.
- **WebhookCog**: Details about WebhookCog functionality, strengths, and weaknesses. See above for details.
- **InferorCog**: Details about Inferor model, provider, triggers, vision support, temperature, strengths, and weaknesses. See above for details.
- **Claude-3-HaikuCog**: This cog interacts with the Claude-3-5-Haiku model via the OpenPipe API, specializing in generating haiku poems. See above for details.
- **DeepseekCog**: This cog interacts with the Deepseek model via the OpenPipe API. See above for details.
- **LlamaVisionCog**: This cog interacts with the LlamaVision model via the OpenPipe API, specializing in image analysis. See above for details.
- **MagnumCog**: This cog interacts with the Magnum model via the OpenPipe API. See above for details.
- **QwenCog**: This cog interacts with the Qwen model via the OpenPipe API. See above for details.
- **RocinanteCog**: This cog interacts with the Rocinante model via the OpenPipe API. See above for details.
- **SonarCog**: This cog interacts with the Sonar model via the OpenPipe API, specializing in current events and real-time information retrieval.  It retrieves citations from the API response and includes them in the output. See above for details.
- **SorcererCog**: This cog interacts with the Sorcerer model via the OpenPipe API. See above for details.
- **SYDNEY-COURTCog**: This cog interacts with the SYDNEY-COURT model via the OpenPipe API. See above for details.
- **UnslopCog**: This cog interacts with the UnslopNemo model via the OpenPipe API, handling medium-length interactions with group scenes and dialogue.  It formats messages to ensure proper role alternation. See above for details.
- **WizardCog**: This cog interacts with the WizardLM model via the OpenPipe API. See above for details.


### Management Cogs

1. **ManagementCog** (`management_cog.py`)
   - Administrative commands.
   - Bot status management.
   - Channel configuration. See above for details.

2. **WebhookCog** (`cogs/webhook_cog.py`)
   - Handles Discord webhook integrations.  This cog uses the `/hook` command to send messages to configured webhooks. It includes retry logic for rate limits and timeouts.
   - Response broadcasting.
   - Webhook configuration management. See above for details.


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

This section provides a brief overview of the key files within the project and their purpose.

1. **`temperatures.json`**: Model temperature settings. Default: `0.7` if not specified.
2. **`dynamic_prompts.json`**: Custom system prompts per channel. Override default prompts.
3. **`bot_config.json`**: Bot configuration settings. Status display settings. Feature toggles.
4. **`databases/schema.sql`**: SQLite database schema. Context and interaction logging tables.
5. **`activated_channels.json`**: Tracks channels where the bot is activated.
6. **`cogs/*`**: Contains the individual cogs for different AI models and functionalities.
7. **`config/*`**: Contains configuration files for the bot.
8. **`databases/*`**: Contains the database schema and related files.
9. **`docs/*`**: Contains documentation files.
10. **`logs/*`**: Contains log files.
11. **`nexa-sdk/*`**: Contains the Nexa SDK (if applicable).
12. **`prompts/*`**: Contains prompt templates and configurations.
13. **`shared/*`**: Contains shared utility functions and modules.
14. **`static/*`**: Contains static assets like images.
15. **`tests/*`**: Contains unit tests for the project.


## Project Structure

The project is structured as follows:

- **`cogs`**: Contains individual cogs for different AI models and functionalities.
- **`config`**: Contains configuration files for the bot.
- **`databases`**: Contains the database schema and related files.
- **`docs`**: Contains documentation files.
- **`logs`**: Contains log files.
- **`nexa-sdk`**: Contains the Nexa SDK (if applicable).
- **`prompts`**: Contains prompt templates and configurations.
- **`shared`**: Contains shared utility functions and modules.
- **`static`**: Contains static assets like images.
- **`tests`**: Contains unit tests for the project.

## Cogs and Function Summaries

### BaseCog (`cogs/base_cog.py`)

This cog provides the base functionality for other cogs, including message handling, response generation, and interaction with the Discord API.  See above for details.

### ManagementCog (`cogs/management_cog.py`)

This cog provides administrative commands for managing the bot and its settings. See above for details.

### RouterCog (`cogs/router_cog.py`)

This cog is responsible for routing messages to the appropriate cog based on the content of the message.  The routing logic is defined in `router_system_prompt.txt` and considers various factors such as message content, context, and the capabilities of each cog. See above for details.

### HelpCog (`cogs/help_cog.py`)

This cog provides help commands and manages channel activation. See above for details.

### ContextCog (`cogs/context_cog.py`)

This cog manages the conversation context, storing and retrieving messages from a database. See above for details.

### GPT4OCog (`cogs/gpt4o_cog.py`)

This cog interacts with the GPT-4o model via the OpenPipe API. See above for details.

### GrokCog (`cogs/grok_cog.py`)

This cog interacts with the Grok model via the OpenPipe API. See above for details.

### Claude-3-HaikuCog (`cogs/claude3haiku_cog.py`)

This cog interacts with the Claude-3-5-Haiku model via the OpenPipe API, specializing in generating haiku poems. See above for details.

### DeepseekCog (`cogs/deepseek_cog.py`)

This cog interacts with the Deepseek model via the OpenPipe API. See above for details.

### HermesCog (`cogs/hermes_cog.py`)

This cog interacts with the Hermes model via the OpenPipe API, focusing on mental health and crisis support. See above for details.

### InferorCog (`cogs/inferor_cog.py`)

This cog interacts with the Inferor model via the OpenPipe API. See above for details.

### LlamaVisionCog (`cogs/llamavision_cog.py`)

This cog interacts with the LlamaVision model via the OpenPipe API, specializing in image analysis. See above for details.

### MagnumCog (`cogs/magnum_cog.py`)

This cog interacts with the Magnum model via the OpenPipe API. See above for details.

### NemotronCog (`cogs/nemotron_cog.py`)

This cog interacts with the Nemotron model via the OpenPipe API, specializing in technical and code-focused tasks. See above for details.

### QwenCog (`cogs/qwen_cog.py`)

This cog interacts with the Qwen model via the OpenPipe API. See above for details.

### RocinanteCog (`cogs/rocinante_cog.py`)

This cog interacts with the Rocinante model via the OpenPipe API. See above for details.

### SonarCog (`cogs/sonar_cog.py`)

This cog interacts with the Sonar model via the OpenPipe API, specializing in current events and real-time information retrieval.  It retrieves citations from the API response and includes them in the output. See above for details.

### SorcererCog (`cogs/sorcerer_cog.py`)

This cog interacts with the Sorcerer model via the OpenPipe API. See above for details.

### SYDNEY-COURTCog (`cogs/sydney_cog.py`)

This cog interacts with the SYDNEY-COURT model via the OpenPipe API. See above for details.

### UnslopCog (`cogs/unslop_cog.py`)

This cog interacts with the UnslopNemo model via the OpenPipe API, handling medium-length interactions with group scenes and dialogue.  It formats messages to ensure proper role alternation. See above for details.

### WebhookCog (`cogs/webhook_cog.py`)

This cog handles Discord webhook integrations, allowing for broadcasting messages to configured webhooks. It includes retry logic for rate limits and timeouts. See above for details.

### WizardCog (`cogs/wizard_cog.py`)

This cog interacts with the WizardLM model via the OpenPipe API.

**Classes:**

* **`WizardCog`**: This class inherits from `BaseCog` and provides the following functions:
    * **`__init__`**: Initializes the cog with specific settings for Wizard.
    * **`qualified_name`**: Returns the cog's name.
    * **`get_temperature`**: Returns the temperature setting for this cog.
    * **`generate_response`**: Generates a response using the OpenPipe API, incorporating conversation history from the database.
