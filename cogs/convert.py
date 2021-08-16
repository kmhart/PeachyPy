from money import Money
from discord.ext import commands
from peachykey import *
from datetime import datetime
from decimal import *
import pint

# to do: help


class Convert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.exchange = None
        self.last_pull = None
        self.ureg = pint.UnitRegistry()
        self.Q_ = self.ureg.Quantity
        self.session = bot.session
        self.logger = bot.logger

    @commands.command(aliases=("$",))
    # convert one currency to another
    async def currency(self, ctx, value: float, code1: str, code2: str):
        value = Decimal(value)
        code1 = code1.upper()
        code2 = code2.upper()
        if self.exchange is None or (datetime.now() - self.last_pull).seconds > 3600:
            async with self.session.get(f"https://openexchangerates.org/api/latest.json?app_id={EXCHANGE_KEY}") \
                    as resp:
                self.exchange = await resp.json()
            self.last_pull = datetime.now()

        if code1 not in self.exchange["rates"] or code2 not in self.exchange["rates"]:
            await ctx.send("One of your currency codes is invalid!")
        else:
            rate = Decimal(self.exchange["rates"][code2])
            if code1 == "USD":
                x_value = value * rate
            else:
                x_value = value / Decimal(self.exchange["rates"][code1]) * rate
            x_value = Money(x_value, code2)
            await ctx.send(x_value.format("en_US"))

    @commands.command()
    # convert any unit using pint registry
    async def convert(self, ctx, value: float, unit1: str, unit2: str):
        try:
            new_value = str(self.Q_(value, self.ureg.parse_expression(unit1)).to(unit2))
            await ctx.send(new_value)
        except pint.UndefinedUnitError:
            await ctx.send("I couldn't find one or both of those units.")
        except pint.DimensionalityError:
            await ctx.send("I can't convert between those units.")
        except Exception as error:
            self.logger.error(error)


def setup(bot):
    bot.add_cog(Convert(bot))
