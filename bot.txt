import os
import json
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
# STATE FILE
# =====================
STATE_FILE = "inventory_state.json"

# =====================
# CONFIG
# =====================
HEARTBEAT_MINUTES = 10
INVENTORY_REFRESH_MINUTES = 5

# =====================
# SHEET COLUMN INDEXES
# =====================
COL_ITEM = 0
COL_QTY = 1
COL_COUNTRY = 2

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
    "Hawaii": "<:ushi:1458203802342522981>",
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
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# STATE HANDLING
# =====================
def load_state():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("posted_message_ids", [])
    except Exception:
        return []

def save_state(ids):
    with open(STATE_FILE, "w") as f:
        json.dump({"posted_message_ids": ids}, f, indent=2)

posted_message_ids = load_state()

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

def country_emoji(country):
    return COUNTRY_EMOJIS.get(country, "🌍")

def qty_bar(current, target, width=5):
    if target <= 0:
        return "⬛" * width
    ratio = current / target
    filled = min(round(ratio * width), width)
    emoji = "🟦" if current >= target else "🟩"
    return emoji * filled + "⬜" * (width - filled)

def parse_inventory(values, target):
    items = []
    for row in values[1:]:
        try:
            items.append({
                "item": row[COL_ITEM],
                "qty": int(row[COL_QTY] or 0),
                "country_emoji": country_emoji(row[COL_COUNTRY]),
                "target": target,
            })
        except Exception:
            continue
    return items

def build_inventory_embeds(inventories):
    embeds = []
    for name, data in inventories.items():
        items = sorted(data["snapshot"], key=lambda i: i["qty"])
        for i in range(0, len(items), 25):
            embed = discord.Embed(
                title=f"{data['emoji']} {name} — Target {data['target']}",
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc)
            )
            for item in items[i:i + 25]:
                embed.add_field(
                    name=f"{item['country_emoji']} {item['item']}",
                    value=f"Qty: **{item['qty']}** {qty_bar(item['qty'], data['target'])}",
                    inline=False
                )
            embed.set_footer(text="Auto-updates every 5 minutes")
            embeds.append(embed)
    return embeds

# =====================
# CORE INVENTORY LOGIC
# =====================
async def refresh_inventory():
    global posted_message_ids

    channel = bot.get_channel(INVENTORY_CHANNEL_ID)
    if not channel:
        return False

    inventories = {}
    for name, cfg in INVENTORIES.items():
        values = get_range(INVENTORY_SHEET, cfg["range"])
        if not values:
            continue
        inventories[name] = {
            "snapshot": parse_inventory(values, get_cell_value(INVENTORY_SHEET, cfg["target_cell"])),
            "target": get_cell_value(INVENTORY_SHEET, cfg["target_cell"]),
            "emoji": cfg["emoji"],
        }

    embeds = build_inventory_embeds(inventories)
    if not embeds:
        return False

    old_messages = []
    for msg_id in posted_message_ids:
        try:
            old_messages.append(await channel.fetch_message(msg_id))
        except Exception:
            pass

    new_ids = []

    try:
        for i, embed in enumerate(embeds):
            if i < len(old_messages):
                await old_messages[i].edit(embed=embed)
                new_ids.append(old_messages[i].id)
            else:
                msg = await channel.send(embed=embed)
                new_ids.append(msg.id)

        for msg in old_messages[len(embeds):]:
            await msg.delete()

    except Exception:
        return await repost_inventory()

    posted_message_ids = new_ids
    save_state(posted_message_ids)
    return True

async def repost_inventory():
    global posted_message_ids

    channel = bot.get_channel(INVENTORY_CHANNEL_ID)
    if not channel:
        return False

    for msg_id in posted_message_ids:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass

    posted_message_ids = []
    save_state([])

    return await refresh_inventory()

# =====================
# TASKS
# =====================
@tasks.loop(minutes=INVENTORY_REFRESH_MINUTES)
async def inventory_task():
    success = await refresh_inventory()
    if not success:
        print("⚠️ Inventory refresh failed — auto-repost attempted")

@tasks.loop(minutes=HEARTBEAT_MINUTES)
async def heartbeat_task():
    print(f"💓 Heartbeat OK | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

# =====================
# SLASH COMMANDS
# =====================
@bot.tree.command(name="inventory-refresh", description="Force inventory refresh")
async def inventory_refresh(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ok = await refresh_inventory()
    await interaction.followup.send(
        "✅ Inventory refreshed" if ok else "❌ Refresh failed",
        ephemeral=True
    )

@bot.tree.command(name="inventory-repost", description="Delete & repost inventory (failsafe)")
async def inventory_repost(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ok = await repost_inventory()
    await interaction.followup.send(
        "🧨 Inventory reposted from scratch" if ok else "❌ Repost failed",
        ephemeral=True
    )

# =====================
# EVENTS
# =====================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()

    if not inventory_task.is_running():
        inventory_task.start()

    if not heartbeat_task.is_running():
        heartbeat_task.start()

# =====================
# RUN
# =====================
bot.run(DISCORD_TOKEN)
