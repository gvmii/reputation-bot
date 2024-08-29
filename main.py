import nextcord
from nextcord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os
from typing import Optional
from datetime import datetime, timedelta

TESTING_GUILD_ID = 1084367607982993428
intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    status=nextcord.Status.do_not_disturb,
    activity=nextcord.Game(name="https://github.com/gvmii"),
    intents=intents,
)
load_dotenv()

con = sqlite3.connect("data/database.db")
cur = con.cursor()

# Cooldown tracking
cooldowns = {}
COOLDOWN_DURATION = timedelta(seconds=1800)

# Define role IDs for reputation thresholds
REPUTATION_ROLE_IDS = {
    50: 1278624804982755339,  # Example role ID for reputation >= 50
    -50: 1278624914559209525,  # Example role ID for reputation <= -50
}

# Define role IDs that bypass the cooldown
BYPASS_COOLDOWN_ROLES = [1144375743183339642]

# User ID with special privileges
SPECIAL_USER_ID = 483056864355942405


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


async def get_reppower(ctx, user_id: int):
    DIVINIDAD_ID = 1204241778304225340
    SUPREMO_ID = 1204241745504768051
    MISTICO_ID = 1204241397352497194
    LVL_30_ID = 1100091149772922910
    LVL_40_ID = 1100091073759547422
    LVL_50_ID = 1154927585512407140
    TEST_ID = 1178025421363761322

    # Fetch the current reppower from the database
    cur.execute("SELECT reppower FROM userrep WHERE user_id = ?", (user_id,))
    result = cur.fetchone()

    if result is None:
        return None

    current_reppower = result[0]
    guild = ctx.guild
    member = guild.get_member(user_id)

    new_reppower = current_reppower
    if nextcord.utils.get(member.roles, id=DIVINIDAD_ID) or nextcord.utils.get(
        member.roles, id=LVL_50_ID
    ):
        new_reppower = 7
    elif nextcord.utils.get(member.roles, id=SUPREMO_ID) or nextcord.utils.get(
        member.roles, id=LVL_40_ID
    ):
        new_reppower = 5
    elif nextcord.utils.get(member.roles, id=MISTICO_ID) or nextcord.utils.get(
        member.roles, id=LVL_30_ID
    ):
        new_reppower = 3
    elif nextcord.utils.get(member.roles, id=TEST_ID):
        new_reppower = 3

    if new_reppower != current_reppower:
        cur.execute(
            """
            UPDATE userrep
            SET reppower = ?
            WHERE user_id = ?
            """,
            (new_reppower, user_id),
        )
        con.commit()

    return new_reppower


async def check_user_exists(user_id: int):
    cur.execute("SELECT user_id FROM userrep WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    return result is not None


async def create_user(user_id: int):
    initial_reputation = 0
    initial_reppower = 1
    cur.execute(
        """
        INSERT INTO userrep (user_id, reputation, reppower, pos_rep, neg_rep, rep_given)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, initial_reputation, initial_reppower, 0, 0, 0),
    )
    con.commit()


async def check_cooldown(user_id: int, guild: nextcord.Guild) -> Optional[float]:
    now = datetime.now()

    # Get member object
    member = guild.get_member(user_id)
    if member is None:
        return None

    # Check if the user has any of the bypass roles
    if any(
        nextcord.utils.get(member.roles, id=role_id)
        for role_id in BYPASS_COOLDOWN_ROLES
    ):
        return None  # Bypass cooldown

    # Check cooldown for users without bypass roles
    if user_id in cooldowns:
        last_used = cooldowns[user_id]
        if now < last_used + COOLDOWN_DURATION:
            remaining = (last_used + COOLDOWN_DURATION - now).total_seconds()
            return remaining
    return None


async def update_cooldown(user_id: int):
    cooldowns[user_id] = datetime.now()


async def update_roles(member: nextcord.Member, reputation: int):
    guild = member.guild

    # Remove all roles associated with reputation levels
    for role_id in REPUTATION_ROLE_IDS.values():
        role = guild.get_role(role_id)
        if role in member.roles:
            await member.remove_roles(role)

    # Add role based on the reputation
    if reputation >= 50:
        role_id = REPUTATION_ROLE_IDS[50]
    elif reputation <= -50:
        role_id = REPUTATION_ROLE_IDS[-50]
    else:
        role_id = None

    if role_id:
        role = guild.get_role(role_id)
        if role:
            await member.add_roles(role)


@bot.slash_command(guild_ids=[TESTING_GUILD_ID])
async def masrep(
    ctx,
    user: nextcord.Member,
    amount: Optional[int] = nextcord.SlashOption(required=False),
):
    user_id = ctx.user.id
    tagged_user_id = user.id

    # Ensure both the command invoker and mentioned user exist in the database
    if not await check_user_exists(user_id):
        await create_user(user_id)
    if not await check_user_exists(tagged_user_id):
        await create_user(tagged_user_id)

    # Check if the author is the special user with unrestricted reputation giving
    if user_id != SPECIAL_USER_ID:
        remaining_cooldown = await check_cooldown(user_id, ctx.guild)
        if remaining_cooldown is not None:
            await ctx.send(
                f"¡Estás en cooldown! Intenta de nuevo en {remaining_cooldown:.2f} segundos."
            )
            return

        # Update cooldown
        await update_cooldown(user_id)

        # Get reppower and set amount
        reppower = await get_reppower(ctx, user_id)
        if reppower is None:
            await ctx.send("Error al recuperar el poder de reputación.")
            return

        # Default to maximum reppower if no amount is given, otherwise use the specified amount
        if amount is None or amount > reppower:
            amount = reppower

    if tagged_user_id == user_id:
        await ctx.send("No puedes darte reputación a ti mismo.")
        return

    if user_id == SPECIAL_USER_ID:
        # Special user can give any amount
        amount = min(
            amount if amount is not None else 1000000, 1000000
        )  # Adjust this number as needed for a reasonable cap

    cur.execute(
        """
        UPDATE userrep
        SET reputation = reputation + ?,
            pos_rep = pos_rep + 1
        WHERE user_id = ?
        """,
        (amount, tagged_user_id),
    )

    cur.execute(
        """
        UPDATE userrep
        SET rep_given = rep_given + 1
        WHERE user_id = ?
        """,
        (user_id,),
    )

    con.commit()

    # Update roles for the tagged user
    tagged_user = ctx.guild.get_member(tagged_user_id)
    if tagged_user:
        cur.execute(
            "SELECT reputation FROM userrep WHERE user_id = ?", (tagged_user_id,)
        )
        reputation_result = cur.fetchone()
        if reputation_result:
            reputation = reputation_result[0]
            await update_roles(tagged_user, reputation)

    await ctx.send(f"{ctx.user.mention} dio {amount} +rep a {user.mention}!")


@bot.slash_command(guild_ids=[TESTING_GUILD_ID])
async def menosrep(
    ctx,
    user: nextcord.Member,
    amount: Optional[int] = nextcord.SlashOption(required=False),
):
    tagged_user_id = user.id
    author_user_id = ctx.user.id

    # Ensure both the command invoker and mentioned user exist in the database
    if not await check_user_exists(author_user_id):
        await create_user(author_user_id)
    if not await check_user_exists(tagged_user_id):
        await create_user(tagged_user_id)

    # Check if the author is the special user with unrestricted reputation removal
    if author_user_id != SPECIAL_USER_ID:
        remaining_cooldown = await check_cooldown(author_user_id, ctx.guild)
        if remaining_cooldown is not None:
            await ctx.send(
                f"¡Estás en cooldown! Intenta de nuevo en {remaining_cooldown:.2f} segundos."
            )
            return

        # Update cooldown
        await update_cooldown(author_user_id)

        # Get reppower and set amount
        reppower = await get_reppower(ctx, author_user_id)
        if reppower is None:
            await ctx.send("Error al recuperar el poder de reputación.")
            return

        # Default to maximum reppower if no amount is given, otherwise use the specified amount
        if amount is None or amount > reppower:
            amount = reppower

    if tagged_user_id == author_user_id:
        await ctx.send("No puedes darte reputación a ti mismo.")
        return

    if author_user_id == SPECIAL_USER_ID:
        # Special user can remove any amount
        amount = min(
            amount if amount is not None else 1000000, 1000000
        )  # Adjust this number as needed for a reasonable cap

    cur.execute(
        """
        UPDATE userrep
        SET reputation = reputation - ?,
            neg_rep = neg_rep + 1
        WHERE user_id = ?
        """,
        (amount, tagged_user_id),
    )

    cur.execute(
        """
        UPDATE userrep
        SET rep_given = rep_given + 1
        WHERE user_id = ?
        """,
        (author_user_id,),
    )

    con.commit()

    # Update roles for the tagged user
    tagged_user = ctx.guild.get_member(tagged_user_id)
    if tagged_user:
        cur.execute(
            "SELECT reputation FROM userrep WHERE user_id = ?", (tagged_user_id,)
        )
        reputation_result = cur.fetchone()
        if reputation_result:
            reputation = reputation_result[0]
            await update_roles(tagged_user, reputation)

    await ctx.send(f"{ctx.user.mention} dio {amount} -rep a {user.mention}!")

    @bot.slash_command(guild_ids=[TESTING_GUILD_ID])
    async def rep_stats(
        ctx, user: Optional[nextcord.Member] = nextcord.SlashOption(required=False)
    ):
        if user is None:
            user = ctx.user

        if not await check_user_exists(user.id):
            await create_user(user.id)

        await get_reppower(ctx, user.id)
        cur.execute(
            """
        SELECT reputation, reppower, pos_rep, neg_rep, rep_given
        FROM userrep
        WHERE user_id = ?
        """,
            (user.id,),
        )
        result = cur.fetchone()

        reputation, reppower, pos_rep, neg_rep, rep_given = result

        embed = nextcord.Embed(title=f"Reputación de {user.name}", color=0xEC0006)
        embed.add_field(name="Reputación", value=reputation, inline=True)
        embed.add_field(name="Poder de rep", value=reppower, inline=True)
        embed.add_field(
            name="Veces que recibió rep positiva", value=pos_rep, inline=True
        )
        embed.add_field(
            name="Veces que recibió rep negativa", value=neg_rep, inline=True
        )
        embed.add_field(name="Veces que ha dado rep", value=rep_given, inline=True)
        embed.set_footer(text="Creado por @megvmi")
        await ctx.send(embed=embed)


bot.run(os.getenv("TOKEN"))
