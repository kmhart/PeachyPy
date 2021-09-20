from discord.ext import tasks, commands
import discord
import sqlite3
import random
import asyncio
import os
import uuid
from xlsxwriter.workbook import Workbook
from peachykey import MON_CHANNEL

# to do: create demon class


class Mon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_conn = sqlite3.connect("peachyDB.db")
        self.db_csr = self.db_conn.cursor()
        self.current_dmn = None
        self.caught = False
        self.attempted = []
        self.pull_demon.start()

    # ------------------- database functions -------------------

    def get_demon(self, demon):
        # return demon tuple, search by parameter name or ID
        if isinstance(demon, str):
            with self.db_conn:
                self.db_csr.execute("SELECT * FROM DEMONS WHERE NAME=? COLLATE NOCASE", (demon,))
                demon = self.db_csr.fetchone()
        else:
            with self.db_conn:
                self.db_csr.execute("SELECT * FROM DEMONS WHERE DEMON_ID=?", (demon,))
                demon = self.db_csr.fetchone()
        return demon

    def has_persona(self, dmn_id, usr_id):
        # does user have this persona? bool
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM PERSONA WHERE DEMON_ID=? AND USER_ID=?", (dmn_id, usr_id))
            check = self.db_csr.fetchone()
        return check is not None

    def is_registered(self, usr_id):
        # is user registered? bool
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM USERS WHERE USER_ID=?", (usr_id,))
            check = self.db_csr.fetchone()
        return check is not None

    def get_starter(self):
        # get tuple of all 3 starter persona
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM DEMONS WHERE DEMON_ID IN (107, 170, 172)")
            group = self.db_csr.fetchall()
        return group

    def register_usr(self, usr_id, starter_id):
        # insert new user into database
        with self.db_conn:
            self.db_csr.execute("INSERT INTO USERS (USER_ID, LEVEL) VALUES (?, 0)", (usr_id,))
            self.db_csr.execute("INSERT INTO PERSONA (USER_ID, DEMON_ID, QTY) VALUES (?, ?, 1)", (usr_id, starter_id))
            self.db_conn.commit()

    def add_persona(self, dmn_id, usr_id):
        # add new persona to user's inventory
        with self.db_conn:
            if self.has_persona(dmn_id, usr_id):
                self.db_csr.execute("UPDATE PERSONA SET QTY=QTY + 1 WHERE USER_ID=? AND DEMON_ID=?", (usr_id, dmn_id))
            else:
                self.db_csr.execute("INSERT INTO PERSONA (USER_ID, DEMON_ID, QTY) VALUES (?, ?, 1)", (usr_id, dmn_id))
            self.db_conn.commit()

    def evolved(self, usr_id):
        # is user's starter evolved? bool
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM PERSONA WHERE USER_ID=? AND DEMON_ID IN (107, 170, 172)", (usr_id,))
            check = self.db_csr.fetchone()
        return check is None

    def get_evolved(self, usr_id):
        # find a user's evolved starter and return its corresponding tuple
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM PERSONA WHERE USER_ID=? AND DEMON_ID IN (85, 171, 173)", (usr_id,))
            persona = self.db_csr.fetchone()

            persona = self.get_demon(persona[1])
        return persona

    def get_qty(self, dmn_id, usr_id):
        # get user qty of persona
        with self.db_conn:
            self.db_csr.execute("SELECT QTY FROM PERSONA WHERE USER_ID=? AND DEMON_ID=?", (usr_id, dmn_id))
            qty = self.db_csr.fetchone()[0]
        return qty

    def remove_persona(self, dmn_id, usr_id):
        # remove persona from user's inventory
        with self.db_conn:
            if self.get_qty(dmn_id, usr_id) > 1:
                self.db_csr.execute("UPDATE PERSONA SET QTY=QTY - 1 WHERE USER_ID=? AND DEMON_ID=?", (usr_id, dmn_id))
            else:
                self.db_csr.execute("DELETE FROM PERSONA WHERE USER_ID=? AND DEMON_ID=?", (usr_id, dmn_id))
            self.db_conn.commit()

    def get_level(self, usr_id):
        # get user's current level
        with self.db_conn:
            self.db_csr.execute("SELECT LEVEL FROM USERS WHERE USER_ID=?", (usr_id,))
            level = self.db_csr.fetchone()
        return level[0]

    def random_rarity(self, rarity):
        # grab random demon of chosen rarity
        with self.db_conn:
            self.db_csr.execute("SELECT * FROM DEMONS WHERE RARITY=?", (rarity,))
            batch = self.db_csr.fetchall()

        demon = random.choice(batch)
        return demon

    async def update_level(self, usr_id):
        # update user's level depending on current persona count
        # evolve starter if user meets requirements (level 10)
        # did this user's starter evolve? return bool
        evolve = False

        with self.db_conn:
            self.db_csr.execute("SELECT COUNT(*) FROM PERSONA WHERE USER_ID=?", (usr_id,))
            count = self.db_csr.fetchone()[0]
            level = int(count / 22)
            self.db_csr.execute("UPDATE USERS SET LEVEL=? WHERE USER_ID=?", (level, usr_id))

            if (level == 10) and not self.evolved(usr_id):
                evolve = True
                self.db_csr.execute("SELECT * FROM PERSONA WHERE USER_ID=? AND DEMON_ID IN (107, 170, 172)", (usr_id,))
                starter = self.db_csr.fetchone()

                if starter[0] == 107:
                    self.remove_persona(107, usr_id)
                    self.add_persona(85, usr_id)
                elif starter[0] == 170:
                    self.remove_persona(170, usr_id)
                    self.add_persona(171, usr_id)
                else:
                    self.remove_persona(172, usr_id)
                    self.add_persona(173, usr_id)
            self.db_conn.commit()
        return evolve

    async def get_inventory(self, usr_id):
        # create excel sheet of user's inventory
        with self.db_conn:
            # database join
            self.db_csr.execute("""SELECT DEMONS.DEMON_ID, DEMONS.NAME, DEMONS.IMG, DEMONS.ELEMENT, DEMONS.ELEMENT_WK, 
            DEMONS.MIN_RANGE, DEMONS.MAX_RANGE, DEMONS.RARITY, PERSONA.QTY
            FROM PERSONA
            LEFT JOIN DEMONS ON PERSONA.DEMON_ID=DEMONS.DEMON_ID
            WHERE USER_ID=?
            ORDER BY RARITY;""", (usr_id,))
            inventory = self.db_csr.fetchall()

        # pull starter for editing
        first = list(inventory[0])
        starter = ("Maia", "Orpheus", "Izanagi")
        if first[0] in starter:
            level = self.get_level(usr_id)
            first[4] = first[4] + (level * 10)
            first[5] = first[5] + (level * 10)

        # excel workbook
        filename = os.path.join("inventory", f"{uuid.uuid4().hex}.xlsx")
        workbook = Workbook(filename, {'constant memory': True})
        with workbook:
            worksheet = workbook.add_worksheet()

            bold = workbook.add_format({'bold': True})
            worksheet.set_column(0, 0, 15)
            worksheet.set_column(1, 2, 30)
            worksheet.set_column(3, 8, 15)

            # write headers
            headers = ("Persona ID", "Persona", "Image", "Element", "Element Weak",
                       "Min Attack", "Max Attack", "Rarity", "Quantity")
            for i, header in enumerate(headers):
                worksheet.write(0, i, header, bold)

            # write first row
            for i, value in enumerate(first):
                if i == 2:
                    value = f"https://i.imgur.com/{value}"
                worksheet.write(1, i, value)

            # write remaining inventory, skipping first row (we wrote this already)
            if len(inventory) > 1:
                for i, row in enumerate(inventory, start=1):
                    if i == 1:
                        continue
                    for j, value in enumerate(row):
                        if j == 2:
                            value = f"https://i.imgur.com/{value}"
                        worksheet.write(i, j, value)
        return filename

    # ------------------ discord embeds -------------------------

    def current_embed(self):
        # embed for rotating demon
        loc = os.path.join("persona", self.current_dmn[5])
        file = discord.File(loc, filename=self.current_dmn[5])

        embed = discord.Embed(title="A demon appears!",
                              description=f"Rank {self.current_dmn[4]} demon {self.current_dmn[1]} appears!")
        embed.set_image(url=f"attachment://{self.current_dmn[5]}")
        return embed, file

    def starter_embed(self, starter):
        # embed for starter option
        text = {
            107: ("\"Thou art I... And I am thou... From the sea of thy soul I cometh...  "
                  "I am Orpheus, master of strings...\"", "CHOICE 2: ORPHEUS"),
            170: ("\"I am thou, thou art I... The time has come... Open thy eyes and call forth what is within.\"",
                  "CHOICE 3: IZANAGI"),
            172: ("\"I am thou... Thou art I... I cometh from the sea of thy heart... "
                  "I am the brilliant mother, Maia...\"", "CHOICE 1: MAIA")
        }

        loc = os.path.join("persona", starter[5])
        file = discord.File(loc, filename=starter[5])

        embed = discord.Embed(title=text.get(starter[0])[0], description=text.get(starter[0])[1])
        embed.add_field(name="Affinity", value=f"element: {starter[2]}, weak: {starter[8]}", inline=False)
        embed.add_field(name="Strength", value=f"attack power: {starter[6]} - {starter[7]}", inline=False)
        embed.set_image(url=f"attachment://{starter[5]}")
        return embed, file

    def evolve_embed(self, usr_id):
        # embed for starter evolution
        persona = self.get_evolved(usr_id)

        text = {
            85: "\"I am Messiah... From this day forth, I shall be with you...\"",
            171: "\"Thou art I, and I am thou... From the sea of thy soul, I come... "
                 "From the very moment of my emergence, I have been a guiding light shed to illuminate thy path... "
                 "I am the original god... Izanagi-no-Okami.\"",
            173: "\"I am Artemis... The dim moon goddess who provides you light... "
                 "My pure counterpart... Do not fear your destiny... \""
        }

        loc = os.path.join("persona", persona[5])
        file = discord.File(loc, filename=persona[5])

        embed = discord.Embed(title=text.get(persona[0]),
                              description="The resolution in your heart has awakened a new persona!")
        embed.add_field(name="Affinity", value=f"element: {persona[2]}, weak: {persona[8]}", inline=False)
        embed.add_field(name="Strength", value=f"attack power: {persona[6]} - {persona[7]}", inline=False)
        embed.set_image(url=f"attachment://{persona[5]}")
        return embed, file

    def capture_embed(self, demon):
        # embed upon capture of demon
        loc = os.path.join("persona", demon[5])
        file = discord.File(loc, filename=demon[5])

        embed = discord.Embed(title="I am thou, thou art I!",
                              description=f"{demon[1]} emerges from the sea of your soul!")
        embed.add_field(name="Affinity", value=f"element: {demon[2]}, weak: {demon[8]}", inline=False)
        embed.add_field(name="Strength", value=f"attack power: {demon[6]} - {demon[7]}", inline=False)
        embed.set_image(url=f"attachment://{demon[5]}")
        return embed, file

    # -----------------------------------------------------------

    def cog_unload(self):
        # cleanup
        self.pull_demon.cancel()
        self.db_conn.close()

    def is_channel(ctx):
        # limit cog to this channel
        return ctx.channel.id == MON_CHANNEL

    @commands.group(help="Collect persona. The more you collect, the stronger your base persona will become!")
    @commands.check(is_channel)
    async def persona(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("That's not a valid subcommand! Ask me for help to see more information about this command.")

    @persona.command(help="Register to use the persona command.")
    @commands.check(is_channel)
    async def register(self, ctx):
        # register a new user
        if self.is_registered(ctx.author.id):
            await ctx.send("You're already registered!")
        else:
            await ctx.send("Alright, let's set you up. Choose your starter. . .")

            persona = self.get_starter()

            e1, f1 = self.starter_embed(persona[2])
            e2, f2 = self.starter_embed(persona[0])
            e3, f3 = self.starter_embed(persona[1])

            await ctx.send(embed=e1, file=f1)
            await ctx.send(embed=e2, file=f2)
            await ctx.send(embed=e3, file=f3)

            def check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            except asyncio.TimeoutError:
                # on command timeout
                await ctx.send(f"Cancelling registration for {ctx.author.name}. . .")
            else:
                if msg.content == "1" or msg.content.lower() == "maia":
                    self.register_usr(ctx.author.id, persona[2][0])
                    await ctx.send(f"{ctx.author.name} successfully registered with Maia.")
                elif msg.content == "2" or msg.content.lower() == "orpheus":
                    self.register_usr(ctx.author.id, persona[0][0])
                    await ctx.send(f"{ctx.author.name} successfully registered with Orpheus.")
                elif msg.content == "3" or msg.content.lower() == "izanagi":
                    self.register_usr(ctx.author.id, persona[1][0])
                    await ctx.send(f"{ctx.author.name} successfully registered with Izanagi.")
                else:
                    await ctx.send("I'm looking for a name or a number between 1 and 3. "
                                   "Try the command again and make your choice!")

    @persona.command(help="Send your persona to battle!")
    @commands.check(is_channel)
    async def battle(self, ctx):
        # send persona to battle
        starter = (107, 170, 172)

        def check(m):
            return m.author == ctx.message.author and m.channel == ctx.message.channel

        if self.caught:
            await ctx.send("This demon has already been captured!")
        elif not self.is_registered(ctx.author.id):
            await ctx.send("You haven't registered, yet! You have no persona to send to battle!")
        elif ctx.author.id in self.attempted:
            await ctx.send("You've attempted this fight already!")
        else:
            await ctx.send("It's time for an all out attack! What's the name of the persona you want to send forward?")

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            except asyncio.TimeoutError:
                # command timeout
                await ctx.send("Battle timeout. . .")
            else:
                # grab user's declared persona
                persona = self.get_demon(msg.content)

                if persona is None:
                    await ctx.send("I can't find that persona. . .")
                elif not self.has_persona(persona[0], ctx.author.id):
                    await ctx.send("You don't have that persona!")
                else:
                    # add to attempted after passing all checks
                    self.attempted.append(ctx.author.id)

                    # generate random attack
                    user_attack = random.randint(persona[6], persona[7])
                    demon_attack = random.randint(self.current_dmn[6], self.current_dmn[7])
                    text_user = ""
                    text_demon = ""

                    # calculate new attack if persona is starter
                    if persona[0] in starter:
                        level = self.get_level(ctx.author.id)
                        user_attack = user_attack + (level * 10)

                    # check for matching weak/strong elements
                    if persona[2] == self.current_dmn[8]:
                        user_attack = round(user_attack * 1.5)
                        text_user = "Critical! "
                    if self.current_dmn[2] == persona[8]:
                        demon_attack = round(demon_attack * 1.5)
                        text_demon = "Critical! "

                    # results
                    text = text_user + f"{persona[1]} attacks for {user_attack}!\n" + \
                        text_demon + f"{self.current_dmn[1]} attacks for {demon_attack}!\n"

                    # check for winners
                    if demon_attack > user_attack:
                        await ctx.send(text + f"{self.current_dmn[1]} defeats you! Retreat and regather your strength!")
                    elif demon_attack == user_attack:
                        await ctx.send(text + "Stalemate! You can still try again!")
                        self.attempted.remove(ctx.author.id)
                    else:
                        # update some stuff and add persona to user's inventory
                        self.caught = True
                        self.add_persona(self.current_dmn[0], ctx.author.id)

                        embed, file = self.capture_embed(self.current_dmn)

                        await ctx.send(text + f"{ctx.author.name} wins! A new persona has emerged!",
                                       embed=embed, file=file)

                        # update user's level, if necessary
                        evolve = await self.update_level(ctx.author.id)
                        if evolve:
                            embed, file = self.evolve_embed(ctx.author.id)
                            await ctx.send("What? Something is happening!",
                                           embed=embed, file=file)

    @persona.command(help="Check your current persona compendium.")
    @commands.check(is_channel)
    async def compendium(self, ctx):
        if not self.is_registered(ctx.author.id):
            await ctx.send("You haven't registered, yet!")
        else:
            # pull inventory (spreadsheet)
            filename = await self.get_inventory(ctx.author.id)

            with open(filename, 'rb') as fp:
                await ctx.send("I've pulled that for you!", file=discord.File(fp, f"{ctx.author.name}Inventory.xlsx"))

            # cleanup
            if os.path.exists(filename):
                os.remove(filename)

    @persona.command(help="Fuse two or more persona. "
                          "Note that a smaller compendium may decrease the strength of your base persona.")
    @commands.check(is_channel)
    async def fuse(self, ctx):
        if not self.is_registered(ctx.author.id):
            await ctx.send("You haven't registered, yet!")
        else:
            # fusion time
            await ctx.send("Welcome to the Velvet Room... "
                           "Fuse two or more persona for the opportunity to gain an even stronger persona. "
                           "Note that this process cannot be undone.\n"
                           "Using space between each value, list the ID numbers of the persona you intend to fuse. "
                           "Repeat for multiple quantities.\nExample: 1 2 3 3\n"
                           "You cannot fuse your starter persona.")

            def check(m):
                return m.author == ctx.message.author and m.channel == ctx.message.channel

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            except asyncio.TimeoutError:
                # command timeout
                await ctx.send("Fusion timeout. . .")
            else:
                # get list of IDs
                batch = list(map(int, msg.content.split()))
                total = 0
                starters = (85, 107, 170, 171, 172, 173)
                names = []

                # flags
                not_found = False
                not_owned = False
                starter_found = False
                invalid_qty = False

                # checks
                for value in batch:
                    demon = self.get_demon(value)
                    count = batch.count(value)
                    if demon is None:
                        not_found = True
                        break
                    elif not self.has_persona(value, ctx.author.id):
                        not_owned = True
                        break
                    elif value in starters:
                        starter_found = True
                        break
                    elif count > self.get_qty(value, ctx.author.id):
                        invalid_qty = True
                        break
                    else:
                        names.append(demon[1])
                        total += demon[7]

                if not_found:
                    await ctx.send("I couldn't find one or more of those persona! Check your IDs again.")
                elif not_owned:
                    await ctx.send("You don't own one or more of those persona!")
                elif starter_found:
                    await ctx.send("You can't fuse your starter!")
                elif invalid_qty:
                    await ctx.send("You've entered an invalid quantity!")
                else:
                    text = ""
                    # confirm before proceeding
                    for value in names:
                        text += f"| {value} "
                    await ctx.send(f"{text}|\nIs this right, {ctx.author.name}?")

                    try:
                        msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        # command timeout
                        await ctx.send("Fusion timeout. . .")
                    else:
                        affirmative = ("yes", "y", "confirm")
                        if msg.content.lower() in affirmative:
                            for value in batch:
                                self.remove_persona(value, ctx.author.id)

                            # calculate rarity
                            if total < 50:
                                rarity = 1
                            elif total < 500:
                                rarity = 2
                            elif total < 1000:
                                rarity = 3
                            else:
                                rarity = 4

                            demon = self.random_rarity(rarity)
                            self.add_persona(demon[0], ctx.author.id)
                            await self.update_level(ctx.author.id)

                            embed, file = self.capture_embed(demon)

                            await ctx.send(f"{ctx.author.name} gained a new persona!",
                                           embed=embed, file=file)
                        else:
                            await ctx.send("Cancelling fusion. . .")

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=6.0)
    async def pull_demon(self):
        # loop to generate new demon for play
        self.caught = False
        self.attempted = []

        rarity = random.randint(0, 1000)
        # 70%, 20%, 7%, 3%
        if rarity <= 700:
            rarity = 1
        elif rarity <= 900:
            rarity = 2
        elif rarity <= 970:
            rarity = 3
        else:
            rarity = 4

        self.current_dmn = self.random_rarity(rarity)

        channel = self.bot.get_channel(MON_CHANNEL)
        embed, file = self.current_embed()
        await channel.send(embed=embed, file=file)

    @pull_demon.before_loop
    async def before_pull(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Mon(bot))
