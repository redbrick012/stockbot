import os
import json
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from sheets import get_sheet_values

# =====================
# ENV
# =====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
INVENTORY_SHEET = os.environ["INVENTORY_SHEET"]
INVENTORY_CHANNEL_ID = int(os.environ["INVENTORY_CHANNEL_ID"])

STATE_FILE = "/app/data/inventory_state.json"
HEARTBEAT_MINUTES = 10

# =====================
# DISCORD
# =====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# STATE
# =====================
posted_message_ids = []

# =====================
# LOAD / SAVE STATE
# =====================
def load_state():
    global posted_message_ids
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            posted_message_ids = json.load(f).get("message_ids", [])
    else:
        posted_message_ids = []

def save_state(ids):
    with open(STATE_FILE, "w") as f:
        json.dump({"message_ids": ids}, f, indent=2)

# =====================
# HELPERS
# =====================
COUNTRY_EMOJIS = {
    "United Kingdom": "🇬🇧",
    "Japan": "🇯🇵",
    "USA": "🇺🇸",
}

def country_emoji(country: str) -> str:
    return COUNTRY_EMOJIS.get(country, "🌍")

def qty_bar(current: int, target: int, width: int = 5) -> str:
    if target <= 0:
        return "⬛" * width

    ratio = current / target
    filled = min(round(ratio * width), width)
    filled_emoji = "🟦" if current >= target else "🟩"
    return filled_emoji * filled + "⬜" * (width - filled)

def parse_inventory(values, target_qty):
    items = []
    for row in values[1:]:
        try:
            items.append({
                "item": row[0],
                "qty": int(row[1] or 0),
                "country_emoji": country_emoji(row[2]),
                "target": target_qty,
            })
        except Exception:
            continue
    return items

def build_inventory_embeds(inventory_snapshots):
    embeds = []

    for name, data in inventory_snapshots.items():
        items = sorted(data["snapshot"], key=lambda i: i["qty"])
        emoji = data["emoji"]
        target = data["target"]

        for i in range(0, len(items), 25):
            chunk = items[i:i + 25]

            embed = discord.Embed(
                title=f"{emoji} {name} Target = {target}",
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc)
            )

            for item in chunk:
                embed.add_field(
                    name=f"{item['country_emoji']} {item['item']}",
                    value=f"Qty: **{item['qty']}** {qty_bar(item['qty'], target)}",
                    inline=False
                )

            embed.set_footer(text="Auto-updates every 5 minutes")
            embeds.append(embed)

    return embeds

# =====================
# HEARTBEAT
# =====================
@tasks.loop(minutes=HEARTBEAT_MINUTES)
async def heartbeat_task():
    print(f"💓 Heartbeat OK | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

# =====================
# CORE REFRESH LOGIC
# =====================
async def refresh_inventory(silent: bool = True):
    global posted_message_ids

    channel = bot.get_channel(INVENTORY_CHANNEL_ID)
    if not channel:
        return False

    values = get_sheet_values(INVENTORY_SHEET)
    if not values:
        return False

    inventories = {
        "Inventory": {
            "snapshot": parse_inventory(values, target_qty=900),
            "target": 900,
            "emoji": "📦",
        }
    }

    embeds = build_inventory_embeds(inventories)
    if not embeds:
        return False

    new_ids = []

    for i, embed in enumerate(embeds):
        try:
            if i < len(posted_message_ids):
                msg = await channel.fetch_message(posted_message_ids[i])
                await msg.edit(embed=embed)  # 🔕 silent edit
                new_ids.append(msg.id)
            else:
                raise IndexError
        except Exception:
            msg = await channel.send(embed=embed)
            new_ids.append(msg.id)

    # Delete extras
    for old_id in posted_message_ids[len(embeds):]:
        try:
            msg = await channel.fetch_message(old_id)
            await msg.delete()
        except Exception:
            pass

    posted_message_ids = new_ids
    save_state(posted_message_ids)

    print(f"🔄 Inventory refreshed ({len(new_ids)} embeds)")
    return True

# =====================
# AUTO LOOP
# =====================
@tasks.loop(minutes=5)
async def inventory_task():
    try:
        await refresh_inventory(silent=True)
    except Exception as e:
        print("❌ Inventory loop error:", e)

# =====================
# SLASH COMMAND
# =====================
@bot.tree.command(name="inventory-refresh", description="Force refresh the inventory embeds")
async def inventory_refresh(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    success = await refresh_inventory(silent=True)

    if success:
        await interaction.followup.send("✅ Inventory refreshed.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Refresh failed.", ephemeral=True)

# =====================
# EVENTS
# =====================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    load_state()

    if not inventory_task.is_running():
        inventory_task.start()

    if not heartbeat_task.is_running():
        heartbeat_task.start()

    await bot.tree.sync()

# =====================
# RUN
# =====================
bot.run(DISCORD_TOKEN)
