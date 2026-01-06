import os
import discord
from discord.ext import tasks, commands
from datetime import datetime, timezone

from sheets import get_sheet_values

# =====================
# ENVIRONMENT VARIABLES
# =====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
INVENTORY_SHEET = os.environ["INVENTORY_SHEET"]
INVENTORY_CHANNEL_ID = int(os.environ["INVENTORY_CHANNEL_ID"])

# =====================
# SHEET COLUMN INDEXES
# =====================
COL_ITEM = 0      # ⬅️ MUST be here
COL_QTY = 1
COL_COUNTRY = 2
COL_VALUE = 3
COL_SCARCITY = 4

COL_REGION = 5

# =====================
# INVENTORY CONFIG
# =====================
INVENTORIES = {
    "Plushies": {
        "range": "B3:G16",
        "target_cell": "J4",
        "emoji": "🧸",
    },
    "Flowers": {
        "range": "B20:G31",
        "target_cell": "J21",
        "emoji": "🌸",
    },
}

COUNTRY_EMOJIS = {
    "Torn": "<:city:1458205750617833596>",
    "Mexico": "<:mx:1458203844474572801>",
    "Cayman Islands": "<:ky:1458203876544221459>",
    "Canada": "<:ca:1458204026813415517>",
    "Hawaii": "<:ushi:1458203802342522981>",  # US state, not country
    "United Kingdom": "<:gb:1458203934647910441>",
    "Argentina": "<:ar:1458204051970986170>",
    "Switzerland": "<:ch:1458203997964861590>",
    "Japan": "<:jp:1458203900594094270>",
    "China": "<:cn:1458203968059474042>",
    "UAE": "<:ae:1458203747749728610>",
    "South Africa": "<:za:1458204114524569640>",
}

# =====================
# DISCORD SETUP
# =====================
intents = discord.Intents.default()
intents.emojis = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# STATE
# =====================
previous_snapshot = {}
posted_message_id = None

# =====================
# HELPERS
# =====================
def get_range(sheet_name, cell_range):
    worksheet = get_sheet_values(sheet_name, worksheet_only=True)
    return worksheet.get(cell_range)

def get_cell_value(sheet_name, cell):
    worksheet = get_sheet_values(sheet_name, worksheet_only=True)
    try:
        return int(worksheet.acell(cell).value)
    except Exception:
        return 0

def qty_bar(current: int, target: int, width: int = 5) -> str:
    if target <= 0:
        return "⬛" * width

    ratio = min(current / target, 1)
    filled = round(ratio * width)
    return "🟩" * filled + "⬛" * (width - filled)

def scarcity_icon(level: int) -> str:
    if level <= 3:
        return "🟥"
    if level <= 6:
        return "🟨"
    return "🟩"

def parse_inventory(values, target_qty):
    items = []

    for row in values[1:]:
        if len(row) <= COL_SCARCITY:
            continue

        try:
            country = row[COL_COUNTRY]

            items.append({
                "item": row[COL_ITEM],
                "qty": int(row[COL_QTY] or 0),
                "scarcity": int(row[COL_SCARCITY] or 0),
                "country": country,
                "country_emoji": country_emoji(country),
                "target": target_qty,
            })
        except ValueError:
            continue

    return items

def country_emoji(country: str) -> str:
    return COUNTRY_EMOJIS.get(country, "🌍")

def build_embed(inventory_snapshots):
    embed = discord.Embed(
        title="📦 Inventory Monitor",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )

    for name, data in inventory_snapshots.items():
        emoji = data["emoji"]  # ✅ correct emoji source
        items = data["snapshot"]
        target = data["target"]

        lines = [
            "```",
            "Item             | Qty | Progress",
            "────────────────────────────────────"
        ]

        for item in items:
            qty = item["qty"]
            bar = qty_bar(qty, target)

            flag = item["country_emoji"]
            item_name = item["item"][:15].ljust(15)

            lines.append(
                f"{flag}  {item_name} | "
                f"{qty:<3} | "
                f"{bar}"
            )

        lines.append("```")

        embed.add_field(
            name=f"{emoji} {name}",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(text="Auto-updates every 15 minutes")
    return embed



# =====================
# MAIN LOOP
@tasks.loop(minutes=15)
async def inventory_task():
    global posted_message_id

    channel = bot.get_channel(INVENTORY_CHANNEL_ID)
    if not channel:
        return

    inventories = {}

    for name, cfg in INVENTORIES.items():
        values = get_range(INVENTORY_SHEET, cfg["range"])
        if not values:
            continue

        target = get_cell_value(INVENTORY_SHEET, cfg["target_cell"])
        snapshot = parse_inventory(values, target)

        inventories[name] = {
            "snapshot": snapshot,
            "target": target,
            "emoji": cfg["emoji"],
        }

    if not inventories:
        return

    embed = build_embed(inventories)

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
