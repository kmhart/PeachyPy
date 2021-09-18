from discord.ext import commands
import discord
from peachykey import *
from datetime import datetime
from urllib.parse import quote
from discord_components import Button, ButtonStyle, Interaction
import asyncio
import math
import re
import logging


class Bookmark:
    def __init__(self, current, c_from):
        self.current = current
        self.c_from = c_from


class FFXIV(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start = datetime.now()
        self.session = bot.session
        self.logger = bot.logger

    @commands.group(help="Ask me about FFXIV.")
    async def ff(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("That's not a valid subcommand! Ask me for help to see more information about this command.")

    def clean(self, raw):
        cleaner1 = re.compile("<UIForeground>.*?</UIForeground>")
        cleaner2 = re.compile("<UIGlow>.*?</UIGlow>")
        cleaner3 = re.compile("<.*?>")
        clean_text = re.sub(cleaner1, "", raw)
        clean_text = re.sub(cleaner2, "", clean_text)
        clean_text = re.sub(cleaner3, "", clean_text)
        return clean_text

    @ff.command(help="Look up a crafting recipe")
    async def recipe(self, ctx, *, query: str):
        query = quote(query)
        url = f"https://xivapi.com/search?indexes=recipe&string={query}&limit=1&language=en&private_key={FFXIV_KEY}"

        async with self.session.get(url) as resp:
            result = await resp.json()

        if result["Pagination"]["Results"] > 0:
            recipe_url = result["Results"][0]["Url"]
            async with self.session.get(f"https://xivapi.com{recipe_url}?language=en&private_key={FFXIV_KEY}") as resp:
                self.logger.info(f"Req to https://xivapi.com{recipe_url}")
                recipe = await resp.json()

            recipe_name = recipe["ItemResult"]["Name"] + " "
            recipe_description = self.clean(recipe["ItemResult"]["Description"])
            recipe_icon = recipe["ItemResult"]["IconHD"]
            recipe_patch = recipe["GamePatch"]["Name"]
            recipe_level = recipe["RecipeLevelTable"]["ClassJobLevel"]
            recipe_difficulty = recipe["RecipeLevelTable"]["Difficulty"]
            recipe_durability = recipe["RecipeLevelTable"]["Durability"]
            recipe_quality = recipe["RecipeLevelTable"]["Quality"]
            recipe_stars = recipe["RecipeLevelTable"]["Stars"]
            recipe_control = recipe["RecipeLevelTable"]["SuggestedControl"]
            recipe_craftsmanship = recipe["RecipeLevelTable"]["SuggestedCraftsmanship"]
            recipe_book = ""

            if recipe["SecretRecipeBook"] is not None:
                recipe_book = recipe["SecretRecipeBook"]["Name"]

            for x in range(recipe_stars + 1):
                if x > 0:
                    recipe_name += "⭐"

            ingredients = {}
            ing_text = ""
            stats = f"Level : {recipe_level}\nDifficulty : {recipe_difficulty}\nDurability : {recipe_durability}\n" \
                    f"Quality : {recipe_quality}" \
                    f"\nSuggested Control : {recipe_control}\nSuggested Craftsmanship : {recipe_craftsmanship}"

            for x in range(10):
                if recipe[f"AmountIngredient{x}"] > 0:
                    ingredients[recipe[f"ItemIngredient{x}"]["Name"]] = recipe[f"AmountIngredient{x}"]

            for key, value in ingredients.items():
                ing_text += f"{key} : {value}\n"

            embed = discord.Embed(title=recipe_name, description=recipe_description)
            embed.set_thumbnail(url=f"https://xivapi.com{recipe_icon}")
            embed.set_author(name=recipe_patch)
            embed.add_field(name="Ingredients", value=ing_text)
            embed.add_field(name="Stats", value=stats)
            embed.set_footer(text=recipe_book)

            await ctx.send(embed=embed)

        else:
            await ctx.send("I couldn't find that recipe.")

    async def search_embed(self, page_no: int, url: str, query: str):
        page = ""

        body = {
            "indexes": "item",
            "columns": "Name",
            "body": {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "wildcard": {
                                    "NameCombined_en": f"*{query}*"
                                }
                            }
                        ]
                    }
                },
                "from": page_no,
                "size": 30,
                "sort": [
                    {
                        "Patch": "desc"
                    }
                ]
            }
        }

        async with self.session.get(url, json=body) as resp:
            result = await resp.json()

        result_no = result["Pagination"]["Results"]

        for x in range(result_no):
            page += result["Results"][x]["Name"] + "\n"

        return discord.Embed(title=query, description=page)

    @ff.command(help="Item search")
    async def items(self, ctx, *, query: str):
        url = f"https://xivapi.com/search?language=en&private_key={FFXIV_KEY}"
        page = ""

        body = {
            "indexes": "item",
            "columns": "Name",
            "body": {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "wildcard": {
                                    "NameCombined_en": f"*{query}*"
                                }
                            }
                        ]
                    }
                },
                "from": 0,
                "size": 30,
                "sort": [
                    {
                        "Patch": "desc"
                    }
                ]
            }
        }

        async with self.session.get(url, json=body) as resp:
            result = await resp.json()

        result_no = result["Pagination"]["Results"]
        results_total = result["Pagination"]["ResultsTotal"]
        pages_no = math.ceil(results_total / 30.0)

        if result_no > 0:
            for x in range(result_no):
                page += result["Results"][x]["Name"] + "\n"

            embed = discord.Embed(title=query, description=page)

            bookmark = Bookmark(1, 0)

            async def button_left_callback(inter: Interaction):
                bookmark.current -= 1
                bookmark.c_from -= 30

                if bookmark.current < 1:
                    bookmark.current = pages_no
                    bookmark.c_from = 30 * (pages_no - 1)
                elif bookmark.current > pages_no:
                    bookmark.current = 1
                    bookmark.c_from = 0

                await button_callback(inter)

            async def button_right_callback(inter: Interaction):
                bookmark.current += 1
                bookmark.c_from += 30

                if bookmark.current < 1:
                    bookmark.current = pages_no
                    bookmark.c_from = 30 * (pages_no - 1)
                elif bookmark.current > pages_no:
                    bookmark.current = 1
                    bookmark.c_from = 0

                await button_callback(inter)

            async def button_callback(inter: Interaction):
                await inter.edit_origin(embed=await self.search_embed(page_no=bookmark.c_from, url=url, query=query),
                                        components=[
                    [
                        self.bot.components_manager.add_callback(
                            Button(style=ButtonStyle.blue, emoji="◀"),
                            button_left_callback,
                        ),
                        Button(
                            label=f"Page {bookmark.current}/{pages_no}",
                            disabled=True,
                        ),
                        self.bot.components_manager.add_callback(
                            Button(style=ButtonStyle.blue, emoji="▶"),
                            button_right_callback,
                        ),
                    ]
                ])

            await ctx.send(
                embed=embed,
                delete_after=600.0,
                components=[
                    [
                        self.bot.components_manager.add_callback(
                            Button(style=ButtonStyle.blue, emoji="◀️"),
                            button_left_callback,
                        ),
                        Button(
                            label=f"Page {bookmark.current}/{pages_no}",
                            disabled=True,
                        ),
                        self.bot.components_manager.add_callback(
                            Button(style=ButtonStyle.blue, emoji="▶️"),
                            button_right_callback,
                        ),
                    ]
                ]
            )

        else:
            await ctx.send("I couldn't find any results.")

    @ff.command(help="Look up an item")
    async def item(self, ctx, *, query: str):
        query = quote(query)
        url = f"https://xivapi.com/search?indexes=item&string={query}&limit=1&language=en&private_key={FFXIV_KEY}"

        async with self.session.get(url) as resp:
            result = await resp.json()

        if result["Pagination"]["Results"] > 0:
            item_url = result["Results"][0]["Url"]
            async with self.session.get(f"https://xivapi.com{item_url}?language=en&private_key={FFXIV_KEY}") as resp:
                self.logger.info(f"Req to https://xivapi.com{item_url}")
                item = await resp.json()

                item_name = item["Name"]
                item_desc = self.clean(item["Description"])
                item_icon = item["IconHD"]
                item_patch = item["GamePatch"]["Name"]

                embed = discord.Embed(title=item_name, description=item_desc)
                embed.set_thumbnail(url=f"https://xivapi.com{item_icon}")
                embed.set_author(name=item_patch)

                if item["ItemKind"]["ID"] == 1 or item["ItemKind"]["ID"] == 2:
                    item_class = item["ClassJobCategory"]["Name"]
                    item_phys = item["DamagePhys"]
                    item_mag = item["DamageMag"]
                    item_delay = item["DelayMs"] / 1000.0
                    item_equip = item["LevelEquip"]
                    item_level = item["LevelItem"]
                    stats = ""

                    embed.set_footer(text=item_class)

                    for k, v in item["Stats"].items():
                        value = v["NQ"]
                        stats += f"{k} : +{value}\n"

                    txt = f"Item Level : {item_level}\nEquip Level : {item_equip}\nPhysical Dmg : {item_phys}\n" \
                          f"Magic Dmg : {item_mag}\nDelay : {item_delay}"

                    embed.add_field(name="Stats", value=txt)
                    embed.add_field(name="Bonuses", value=stats)

                    await ctx.send(embed=embed)

                elif item["ItemKind"]["ID"] == 3:
                    item_class = item["ClassJobCategory"]["Name"]
                    item_phys = item["DefensePhys"]
                    item_mag = item["DefenseMag"]
                    item_block = item["Block"]
                    item_blockrate = item["BlockRate"]
                    item_equip = item["LevelEquip"]
                    item_level = item["LevelItem"]
                    stats = ""

                    embed.set_footer(text=item_class)

                    for k, v in item["Stats"].items():
                        value = v["NQ"]
                        stats += f"{k} : +{value}\n"

                    txt = f"Item Level : {item_level}\nEquip Level : {item_equip}\nPhys Defense : {item_phys}\n" \
                          f"Mag Defense : {item_mag}\nBlock : {item_block}\nBlock Rate : {item_blockrate}"

                    embed.add_field(name="Stats", value=txt)
                    embed.add_field(name="Bonuses", value=stats)

                    await ctx.send(embed=embed)

                elif item["ItemKind"]["ID"] == 4:
                    item_class = item["ClassJobCategory"]["Name"]
                    item_equip = item["LevelEquip"]
                    item_level = item["LevelItem"]
                    stats = ""

                    embed.set_footer(text=item_class)

                    for k, v in item["Stats"].items():
                        value = v["NQ"]
                        stats += f"{k} : +{value}\n"

                    txt = f"Item Level : {item_level}\nEquip Level : {item_equip}"

                    embed.add_field(name="Stats", value=txt)
                    embed.add_field(name="Bonuses", value=stats)

                    await ctx.send(embed=embed)

                elif item["ItemKind"]["ID"] == 5:
                    bonuses = ""

                    if "Bonuses" in item.keys():
                        for k, v in item["Bonuses"].items():
                            pct = v["Value"]
                            max_value = v["Max"]
                            bonuses += f"{k} +{pct}% (Max {max_value})\n"

                        embed.add_field(name="Bonuses", value=bonuses, inline=False)

                    await ctx.send(embed=embed)

                elif item["ItemKind"]["ID"] == 6:
                    sold = ""

                    if "GilShopItem" in item["GameContentLinks"].keys():
                        sold = "*This item is sold by NPC."

                    embed.set_footer(text=sold)
                    await ctx.send(embed=embed)

                else:
                    await ctx.send(embed=embed)

        else:
            await ctx.send("I couldn't find that item.")


def setup(bot):
    bot.add_cog(FFXIV(bot))
