import nextcord
from nextcord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os
from typing import Optional
from datetime import datetime, timedelta

TESTING_GUILD_ID = 926231740069068801
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
        # Handle case where the user is not found in the database
        return None

    current_reppower = result[0]
    guild = ctx.guild
    member = guild.get_member(user_id)

    # Determine new reppower based on roles
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

    # Update the database if the reppower has changed
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


async def check_cooldown(user_id: int) -> Optional[float]:
    now = datetime.now()
    if user_id in cooldowns:
        last_used = cooldowns[user_id]
        if now < last_used + COOLDOWN_DURATION:
            remaining = (last_used + COOLDOWN_DURATION - now).total_seconds()
            return remaining
    return None


async def update_cooldown(user_id: int):
    cooldowns[user_id] = datetime.now()


@bot.slash_command(guild_ids=[TESTING_GUILD_ID])
async def masrep(ctx, user: nextcord.Member):
    user_id = ctx.user.id
    tagged_user_id = user.id

    remaining_cooldown = await check_cooldown(user_id)
    if remaining_cooldown is not None:
        await ctx.send(
            f"¡Estás en cooldown! Intenta de nuevo en {remaining_cooldown:.2f} segundos."
        )
        return

    # Update cooldown
    await update_cooldown(user_id)

    if tagged_user_id == user_id:
        await ctx.send("No puedes darte reputación a ti mismo.")
        return

    if not await check_user_exists(user_id):
        await create_user(user_id)

    if not await check_user_exists(tagged_user_id):
        await create_user(tagged_user_id)

    reppower = await get_reppower(ctx, user_id)
    if reppower is None:
        await ctx.send("Error al recuperar el poder de reputación.")
        return

    cur.execute(
        """
        UPDATE userrep
        SET reputation = reputation + ?,
            pos_rep = pos_rep + 1
        WHERE user_id = ?
        """,
        (reppower, tagged_user_id),
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
    await ctx.send(f"{ctx.user.mention} dio {reppower} +rep a {user.mention}!")


@bot.slash_command(guild_ids=[TESTING_GUILD_ID])
async def menosrep(ctx, user: nextcord.Member):
    tagged_user_id = user.id
    author_user_id = ctx.user.id

    remaining_cooldown = await check_cooldown(author_user_id)
    if remaining_cooldown is not None:
        await ctx.send(
            f"¡Estás en cooldown! Intenta de nuevo en {remaining_cooldown:.2f} segundos."
        )
        return

    # Update cooldown
    await update_cooldown(author_user_id)

    if tagged_user_id == author_user_id:
        await ctx.send("No puedes darte reputación a ti mismo.")
        return

    if not await check_user_exists(author_user_id):
        await create_user(author_user_id)

    if not await check_user_exists(tagged_user_id):
        await create_user(tagged_user_id)

    reppower = await get_reppower(ctx, author_user_id)
    if reppower is None:
        await ctx.send("Error al recuperar el poder de reputación.")
        return

    cur.execute(
        """
        UPDATE userrep
        SET reputation = reputation - ?,
            neg_rep = neg_rep + 1
        WHERE user_id = ?
        """,
        (reppower, tagged_user_id),
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
    await ctx.send(f"{ctx.user.mention} dio {reppower} -rep a {user.mention}!")


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
    embed.add_field(name="Veces que recibió rep positiva", value=pos_rep, inline=True)
    embed.add_field(name="Veces que recibió rep negativa", value=neg_rep, inline=True)
    embed.add_field(name="Veces que ha dado rep", value=rep_given, inline=True)
    embed.set_footer(text="Creado por @megvmi")
    await ctx.send(embed=embed)


@bot.event
async def on_application_command_error(ctx: nextcord.Interaction, error: Exception):
    await ctx.send(f"Ocurrió un error: {error}")
    print(f"Ocurrió un error: {error}")


bot.run(os.getenv("TOKEN"))
