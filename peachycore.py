import discord
from discord.ext import commands
from peachykey import *
import aiohttp
from discord_components import DiscordComponents
import logging

# to do: logging timestamps

extensions = ("cogs.mon", "cogs.convert", "cogs.general", "cogs.ffxiv")
prefix = ("peachy ", "Peachy ", "peachypy ", "Peachypy ", "PeachyPy ", "px ", "PX ", "Px ", "!")


class PeachyPy(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix, case_insensitive=True, activity=discord.Game(name="with Python"))

        self.session = aiohttp.ClientSession(loop=self.loop)
        logging.basicConfig(filename="peachylog.log", level=logging.INFO)
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
        if self.extra_events.get('on_command_error', None):
            return

        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog and cog._get_overridden_method(cog.cog_command_error) is not None:
            return

        if isinstance(error, commands.TooManyArguments):
            return await ctx.send("That's too many arguments!")

        if isinstance(error, commands.MissingPermissions) or isinstance(error, commands.MissingRole) \
                or isinstance(error, commands.NotOwner):
            return await ctx.send("Sorry, you don't have the required permissions for this command.")

        if isinstance(error, commands.DisabledCommand):
            return await ctx.send("Sorry, that command is disabled.")

        if isinstance(error, commands.CheckFailure):
            return await ctx.send("Something seems to be missing here. 🤔")

        if isinstance(error, commands.BadArgument) or isinstance(error, commands.ArgumentParsingError):
            return await ctx.send("I don't understand your input. Can you check that and try again?")

        self.logger.warning(error)


if __name__ == "__main__":
    PeachyPy().run(TOKEN)
