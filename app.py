import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1213463478568882176  # ID server bạn muốn sync ngay

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="sc?", intents=intents, help_command=None)

# ---------------- Hàm load tất cả cogs ----------------
async def load_all_cogs():
    cogs_loaded = 0
    if not os.path.exists("./cogs"):
        print("❌ Folder 'cogs' không tồn tại!")
        return
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"⚡ Loaded cog: {filename}")
                cogs_loaded += 1
            except Exception as e:
                print(f"❌ Lỗi load cog {filename}: {e}")
    print(f"✅ Tổng cogs đã load: {cogs_loaded}")

# ---------------- Event on_ready ----------------
@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập: {bot.user}")

    # Sync slash commands cho server trước
    try:
        guild = discord.Object(id=GUILD_ID)
        synced_guild = await bot.tree.sync(guild=guild)
        print(f"🔗 Slash commands synced cho server {GUILD_ID}: {len(synced_guild)}")
    except Exception as e:
        print(f"❌ Lỗi sync guild: {e}")

    # Sync slash commands global sau
    try:
        synced_global = await bot.tree.sync()
        print(f"🌐 Slash commands synced global: {len(synced_global)}")
    except Exception as e:
        print(f"❌ Lỗi sync global: {e}")

# ---------------- Main async runner ----------------
async def main():
    async with bot:
        await load_all_cogs()
        await bot.start(TOKEN)

# ---------------- Chạy bot ----------------
asyncio.run(main())