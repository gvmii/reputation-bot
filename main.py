import nextcord
from nextcord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os

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


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.slash_command(guild_ids=[TESTING_GUILD_ID])
async def rep(ctx, user: nextcord.Member):
    tagged_user_id = user.id
    author_user_id = ctx.user.id
    if tagged_user_id is author_user_id:
        await ctx.send("suicidate")
        return
    # Check if the user already exists in the database
    cur.execute("SELECT user_id FROM userrep WHERE user_id = ?", (tagged_user_id,))
    result = cur.fetchone()

    if result is None:
        # If the user doesn't exist, insert the user with initial reputation and bonus
        initial_reputation = 0
        initial_reputation_bonus = 0

        cur.execute(
            """
            INSERT INTO userrep (user_id, reputation, repbonus)
            VALUES (?, ?, ?)
            """,
            (tagged_user_id, initial_reputation, initial_reputation_bonus),
        )

    # Fetch the reputation bonus of the author user
    cur.execute("SELECT repbonus FROM userrep WHERE user_id = ?", (author_user_id,))
    repbonus = cur.fetchone()

    # Ensure repbonus is not None
    if repbonus is None:
        repbonus = (0,)  # Default to 0 if not found

    # Update the tagged user's reputation with the added points and their reputation bonus
    cur.execute(
        """
        UPDATE userrep
        SET reputation = reputation + ? + ?
        WHERE user_id = ?
        """,
        (1, repbonus[0], tagged_user_id),
    )

    # Commit the changes to the database
    con.commit()

    # Close the connection (commented out since it should remain open for further operations)
    # con.close()


bot.run(os.getenv("TOKEN"))
