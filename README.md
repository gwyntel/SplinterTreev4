# 🌳 SplinterTree v4

A powerful Discord bot that provides access to multiple AI language models with advanced features like shared conversation context, image processing, dynamic prompting, and intelligent message routing.

## ✨ Project Architecture

SplinterTree v4 is designed with a flexible, scalable architecture that enables dynamic AI model interactions:

### Key Architectural Components

- **Modular Cog System**: Supports over 15 different AI models with individual cogs for specialized interactions
- **Dynamic Routing**: Intelligent message routing using RouterCog to select optimal AI models
- **Comprehensive AI Integration Layer**: Centralized API client managing interactions across multiple providers
- **Async Python Framework**: Leverages modern async programming patterns for high-performance interactions

### Core Infrastructure Capabilities

- **Persistent Context Management**: SQLite-based conversation tracking
- **Multi-Provider Support**: Seamless integration with OpenPipe, OpenRouter, and direct model APIs
- **Robust Error Handling**: Comprehensive logging and fallback mechanisms
- **Multimodal Processing**: Supports text, image, and complex input types

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

[Rest of the original README content continues...]
