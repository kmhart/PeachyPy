from discord.ext import commands
from datetime import datetime
from urllib.parse import quote
import json
from peachykey import *


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.logger = bot.logger

    @commands.command()
    async def hello(self, ctx):
        special_em = {
            "January": "🎉",
            "April": "🐇",
            "June": "🌈",
            "October": "🎃",
            "November": "🦃",
            "December": "🎄"
        }
        now = datetime.now()
        emoji = special_em.get(now.strftime("%B"), "🍑")
        await ctx.send(f"Hi there, I'm PeachyPy! 🥰 I look forward to serving you, {ctx.author.name}!\n"
                       f"You can call me at any time with the following prefixes: Peachy, PX\n"
                       f"I have a few tasks available. Call me with the \"help\" command for more information. {emoji}")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.bot.logout()
        self.logger.info("Logged out.")
        exit()


def setup(bot):
    bot.add_cog(General(bot))
