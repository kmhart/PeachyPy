import discord
from discord.ext import commands
from peachykey import *
import aiohttp
from discord_components import DiscordComponents
import logging

# to do: finish error handling
# logging

extensions = ("cogs.mon", "cogs.convert", "cogs.general", "cogs.ffxiv")
prefix = ("peachy ", "Peachy ", "peachypy ", "Peachypy ", "PeachyPy ", "px ", "PX ", "Px")


class PeachyPy(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix, case_insensitive=True, activity=discord.Game(name="with Python"))

        self.session = aiohttp.ClientSession(loop=self.loop)
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("Peachy")
        self.logger.setLevel(logging.INFO)

        for extension in extensions:
            try:
                self.load_extension(extension)
            except Exception as error:
                self.logger.error(f"Failed to load {extension}.", error)

    async def on_ready(self):
        DiscordComponents(self)
        self.logger.info(f"{self.user} ready.")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.TooManyArguments):
            return await ctx.send("Too many arguments!")

        self.logger.warning(error)


if __name__ == "__main__":
    PeachyPy().run(TOKEN)
