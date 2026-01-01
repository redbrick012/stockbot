import os
import discord
from discord.ext import tasks, commands
from datetime import datetime

from sheets import get_sheet_values

# =====================
# ENVIRONMENT VARIABLES
# =====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
INVENTORY_SHEET = os.environ["INVENTORY_SHEET"]
INVENTORY_CHANNEL_ID = int(os.environ["INVENTORY_CHANNEL_ID"])
TARGET_QTY = int(os.environ.get("TARGET_QTY", 200))

# =====================
# SHEET COLUMN INDEXES
# =====================
COL_QTY = 0
COL_COUNTRY = 1
COL_VALUE = 2
COL_SCARCITY = 3
COL_REGION = 5

# =====================
# DISCORD SETUP
# =====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# STATE
# =====================
previous_snapshot = {}
posted_message_id = None

# =====================
# HELPERS
# =====================
def qty_bar(current: int, target: int, width: int = 10) -> str:
    ratio = min(current / target, 1)
    filled = round(ratio * width)
    return "🟩" * filled + "⬛" * (width - filled)

def scarcity_icon(level: int) -> str:
    if level <= 3:
        return "🟥"
    if level <= 6:
        return "🟨"
    return "🟩"

def parse_inventory(values):
    snapshot = {}

    for row in values[1:]:
        if len(row) <= COL_REGION:
            continue

        try:
            region = row[COL_REGION] or "Other"
            country = row[COL_COUNTRY]

            snapshot.setdefault(region, {})[country] = {
                "qty": int(row[COL_QTY] or 0),
                "scarcity": int(row[COL_SCARCITY] or 0),
            }
        except ValueError:
            continue

    return snapshot

def build_embed(snapshot):
    embed = discord.Embed(
        title="📦 Inventory Monitor",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )

    embed.set_thumbnail(url=bot.user.display_avatar.url)

    for region, countries in snapshot.items():
        lines = [
            "```",
            "Country      | Qty | Bar        | Status",
            "────────────────────────────────────"
        ]

        for country, data in countries.items():
            qty = data["qty"]
            bar = qty_bar(qty, TARGET_QTY)
            status = scarcity_icon(data["scarcity"])

            if qty < TARGET_QTY:
                status += " ⚠"

            lines.append(
                f"{country:<12} | "
                f"{qty:<3} | "
                f"{bar} | "
                f"{status}"
            )

        lines.append("```")

        embed.add_field(
            name=f"🌍 {region}",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(
        text=f"Target Qty: {TARGET_QTY} • Auto-updates every 15 minutes"
    )

    return embed

# =====================
# MAIN LOOP
# =====================
@tasks.loop(minutes=15)
async def inventory_task():
    global previous_snapshot, posted_message_id

    channel = bot.get_channel(INVENTORY_CHANNEL_ID)
    if not channel:
        return

    values = get_sheet_values(INVENTORY_SHEET)
    if not values:
        return

    current = parse_inventory(values)

    embed = build_embed(current)

    if posted_message_id:
        try:
            message = await channel.fetch_message(posted_message_id)
            await message.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            posted_message_id = msg.id
    else:
        msg = await channel.send(embed=embed)
        posted_message_id = msg.id

    previous_snapshot = current

# =====================
# EVENTS
# =====================
@bot.event
async def on_ready():
    print(f"✅ Inventory bot logged in as {bot.user}")

    if not inventory_task.is_running():
        inventory_task.start()

# =====================
# RUN
# =====================
bot.run(DISCORD_TOKEN)

