import discord
from discord.ext import commands
import logging

from .base_cog import BaseCog
from shared.utils import get_model_temperature

class Mythomax_cog(BaseCog, name="Mythomax"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot, trigger_words=['[Mythomax]', '[mythomax]'], name="Mythomax", model="gryphe/mythomax-l2-13b", provider="openrouter")
        self.temperature = get_model_temperature("Mythomax")

    @commands.command(name="mythomax", aliases=["Mythomax"])
    async def mythomax_command(self, ctx: commands.Context, *, prompt: str):
        await self.process_command(ctx, prompt, "Mythomax")


    async def cog_load(self):
        try:
            await super().cog_load()
        except Exception as e:
            logging.error(f"[{self.name}] Failed to register cog: {str(e)}")


async def setup(bot):
    try:
        await bot.add_cog(Mythomax_cog(bot))
        logging.info("Loaded cog: Mythomax")
    except Exception as e:
        logging.error(f"Failed to load cog mythomax_cog.py: {str(e)}")
