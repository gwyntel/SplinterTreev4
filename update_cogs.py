import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)

# Base template for all cogs
BASE_TEMPLATE = '''import discord
from discord.ext import commands
import logging
from .base_cog import BaseCog
import json

class {class_name}(BaseCog):
    def __init__(self, bot):
        super().__init__(
            bot=bot,
            name="{name}",
            nickname="{nickname}",
            trigger_words={trigger_words},
            model="{model}",
            provider="{provider}",
            prompt_file="{prompt_file}",
            supports_vision={supports_vision}
        )
        logging.debug(f"[{log_name}] Initialized with raw_prompt: {{self.raw_prompt}}")
        logging.debug(f"[{log_name}] Using provider: {{self.provider}}")
        logging.debug(f"[{log_name}] Vision support: {{self.supports_vision}}")

        # Load temperature settings
        try:
            with open('temperatures.json', 'r') as f:
                self.temperatures = json.load(f)
        except Exception as e:
            logging.error(f"[{log_name}] Failed to load temperatures.json: {{e}}")
            self.temperatures = {{}}

    @property
    def qualified_name(self):
        """Override qualified_name to match the expected cog name"""
        return "{qualified_name}"

    def get_temperature(self):
        """Get temperature setting for this agent"""
        return self.temperatures.get(self.name.lower(), 0.7)'''

# Template for generate_response (same for all models now)
RESPONSE_TEMPLATE = '''
    async def generate_response(self, message):
        """Generate a response using openrouter"""
        try:
            # Format system prompt
            formatted_prompt = self.format_prompt(message)
            messages = [{{"role": "system", "content": formatted_prompt}}]

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
                
                messages.append({{
                    "role": role,
                    "content": content
                }})

            # Add the current message
            messages.append({{
                "role": "user",
                "content": message.content
            }})

            logging.debug(f"[{log_name}] Sending {{len(messages)}} messages to API")
            logging.debug(f"[{log_name}] Formatted prompt: {{formatted_prompt}}")

            # Get temperature for this agent
            temperature = self.get_temperature()
            logging.debug(f"[{log_name}] Using temperature: {{temperature}}")

            # Get user_id and guild_id
            user_id = str(message.author.id)
            guild_id = str(message.guild.id) if message.guild else None

            # Call API and return the stream directly
            response_stream = await self.api_client.call_openpipe(
                messages=messages,
                model=self.model,
                temperature=temperature,
                stream=False, # Changed to False to disable streaming
                provider="{provider}",
                user_id=user_id,
                guild_id=guild_id,
                prompt_file="{prompt_file}"
            )

            return response_stream

        except Exception as e:
            logging.error(f"Error processing message for {name}: {{e}}")
            return None'''

# Template for setup function
SETUP_TEMPLATE = '''
async def setup(bot):
    try:
        cog = {class_name}(bot)
        await bot.add_cog(cog)
        logging.info(f"[{log_name}] Registered cog with qualified_name: {{cog.qualified_name}}")
        return cog
    except Exception as e:
        logging.error(f"[{log_name}] Failed to register cog: {{e}}", exc_info=True)
        raise'''

# Configuration for each cog based on OpenRouter models
COGS_CONFIG = {
    'gpt4o': {
        'class_name': 'GPT4OCog',
        'name': 'GPT-4o',
        'nickname': 'GPT4o',
        'trigger_words': "['gpt4o', '4o', 'openai']",
        'model': 'openpipe:openrouter/openai/gpt-4o-2024-11-20',
        'provider': 'openpipe',
        'prompt_file': 'gpt4o_prompts',
        'supports_vision': 'False',
        'log_name': 'GPT-4o',
        'qualified_name': 'GPT-4o'
    },
    'grok': {
        'class_name': 'GrokCog',
        'name': 'Grok',
        'nickname': 'Grok',
        'trigger_words': "['grok', 'xAI']",
        'model': 'openpipe:openrouter/x-ai/grok-beta',
        'provider': 'openpipe',
        'prompt_file': 'grok_prompts',
        'supports_vision': 'False',
        'log_name': 'Grok',
        'qualified_name': 'Grok'
    },
    'hermes': {
        'class_name': 'HermesCog',
        'name': 'Hermes',
        'nickname': 'Hermes',
        'trigger_words': "['hermes', 'hermes-3', 'nous']",
        'model': 'openpipe:openrouter/nousresearch/hermes-3-llama-3.1-405b',
        'provider': 'openpipe',
        'prompt_file': 'hermes_prompts',
        'supports_vision': 'False',
        'log_name': 'Hermes',
        'qualified_name': 'Hermes'
    },
    'sonar': {
        'class_name': 'SonarCog',
        'name': 'Sonar',
        'nickname': 'Sonar',
        'trigger_words': "['sonar', 'perplexity', 'search']",
        'model': 'openpipe:openrouter/perplexity/llama-3.1-sonar-large-128k-online',
        'provider': 'openpipe',
        'prompt_file': 'sonar_prompts',
        'supports_vision': 'False',
        'log_name': 'Sonar',
        'qualified_name': 'Sonar'
    },
    'wizard': {
        'class_name': 'WizardCog',
        'name': 'Wizard',
        'nickname': 'Wizard',
        'trigger_words': "['wizard', 'wizardlm']",
        'model': 'openpipe:infermatic/WizardLM-2-8x22B',
        'provider': 'openpipe',
        'prompt_file': 'wizard_prompts',
        'supports_vision': 'False',
        'log_name': 'Wizard',
        'qualified_name': 'Wizard'
    },
    'unslop': {
        'class_name': 'UnslopCog',
        'name': 'Unslop',
        'nickname': 'Unslop',
        'trigger_words': "['unslop', 'unslopnemo']",
        'model': 'openpipe:infermatic/TheDrummer-UnslopNemo-12B-v4.1',
        'provider': 'openpipe',
        'prompt_file': 'unslop_prompts',
        'supports_vision': 'False',
        'log_name': 'Unslop',
        'qualified_name': 'Unslop'
    },
    'rocinante': {
        'class_name': 'RocinanteCog',
        'name': 'Rocinante',
        'nickname': 'Rocinante',
        'trigger_words': "['rocinante']",
        'model': 'openpipe:infermatic/TheDrummer-Rocinante-12B-v1.1',
        'provider': 'openpipe',
        'prompt_file': 'rocinante_prompts',
        'supports_vision': 'False',
        'log_name': 'Rocinante',
        'qualified_name': 'Rocinante'
    },
    'sorcerer': {
        'class_name': 'SorcererCog',
        'name': 'Sorcerer',
        'nickname': 'Sorcerer',
        'trigger_words': "['sorcerer', 'sorcererlm']",
        'model': 'openpipe:infermatic/rAIfle-SorcererLM-8x22b-bf16',
        'provider': 'openpipe',
        'prompt_file': 'sorcerer_prompts',
        'supports_vision': 'False',
        'log_name': 'Sorcerer',
        'qualified_name': 'Sorcerer'
    },
    'qwen': {
        'class_name': 'QwenCog',
        'name': 'Qwen',
        'nickname': 'Qwen',
        'trigger_words': "['qwen', 'qwen2.5']",
        'model': 'openpipe:infermatic/Qwen2.5-72B-Instruct-Turbo',
        'provider': 'openpipe',
        'prompt_file': 'qwen_prompts',
        'supports_vision': 'False',
        'log_name': 'Qwen',
        'qualified_name': 'Qwen'
    },
    'nemotron': {
        'class_name': 'NemotronCog',
        'name': 'Nemotron',
        'nickname': 'Nemotron',
        'trigger_words': "['nemotron', 'nvidia']",
        'model': 'openpipe:infermatic/nvidia-Llama-3.1-Nemotron-70B-Instruct-HF',
        'provider': 'openpipe',
        'prompt_file': 'nemotron_prompts',
        'supports_vision': 'False',
        'log_name': 'Nemotron',
        'qualified_name': 'Nemotron'
    },
    'inferor': {
        'class_name': 'InferorCog',
        'name': 'Inferor',
        'nickname': 'Inferor',
        'trigger_words': "['inferor']",
        'model': 'openpipe:infermatic/Infermatic-MN-12B-Inferor-v0.0',
        'provider': 'openpipe',
        'prompt_file': 'inferor_prompts',
        'supports_vision': 'False',
        'log_name': 'Inferor',
        'qualified_name': 'Inferor'
    },
    'magnum': {
        'class_name': 'MagnumCog',
        'name': 'Magnum',
        'nickname': 'Magnum',
        'trigger_words': "['magnum', 'anthracite']",
        'model': 'openpipe:infermatic/anthracite-org-magnum-v4-72b-FP8-Dynamic',
        'provider': 'openpipe',
        'prompt_file': 'magnum_prompts',
        'supports_vision': 'False',
        'log_name': 'Magnum',
        'qualified_name': 'Magnum'
    },
    'llamavision': {
        'class_name': 'LlamaVisionCog',
        'name': 'LlamaVision',
        'nickname': 'LlamaVision',
        'trigger_words': "['llamavision', 'vision', 'image', 'describe this image']",
        'model': 'openpipe:groq/llama-3.2-90b-vision-preview',
        'provider': 'openpipe',
        'prompt_file': 'llamavision_prompts',
        'supports_vision': 'True',
        'log_name': 'LlamaVision',
        'qualified_name': 'LlamaVision'
    },
    'router': {
        'class_name': 'RouterCog',
        'name': 'Router',
        'nickname': 'Router',
        'trigger_words': "[]",
        'model': 'openpipe:openrouter/openai/gpt-4o-2024-11-20',
        'provider': 'openpipe',
        'prompt_file': 'router',
        'supports_vision': 'False',
        'log_name': 'Router',
        'qualified_name': 'Router'
    }
}

def update_cog(cog_name, config):
    """Update a single cog file with the new template"""
    try:
        # Start with the base template
        cog_content = BASE_TEMPLATE.format(**config)

        # Add the response template
        cog_content += RESPONSE_TEMPLATE.format(
            provider=config['provider'],
            log_name=config['log_name'],
            name=config['name'],
            prompt_file=config['prompt_file']
        )

        # Add the setup function
        cog_content += SETUP_TEMPLATE.format(**config)

        # Write to the cog file
        cog_path = f'cogs/{cog_name}_cog.py'
        with open(cog_path, 'w') as f:
            f.write(cog_content)
        logging.info(f"Updated {cog_path}")

    except Exception as e:
        logging.error(f"Error updating {cog_name}: {e}")

def main():
    """Update all cogs with the new template"""
    logging.info("Starting cog updates...")

    # Update each cog
    for cog_name, config in COGS_CONFIG.items():
        update_cog(cog_name, config)

    logging.info("Cog updates completed")

if __name__ == "__main__":
    main()
