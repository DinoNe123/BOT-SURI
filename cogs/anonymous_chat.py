import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import zoneinfo

# Múi giờ Việt Nam
VIETNAM_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")


class ConfirmView(discord.ui.View):
    def __init__(self, cog, sender: discord.User, receiver: discord.User):
        super().__init__(timeout=60)
        self.cog = cog
        self.sender = sender
        self.receiver = receiver

    @discord.ui.button(label="Đồng ý ✅", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.active_sessions[self.sender.id] = self.receiver.id
        self.cog.active_sessions[self.receiver.id] = self.sender.id
        key = tuple(sorted([self.sender.id, self.receiver.id]))
        self.cog.last_message_time[key] = datetime.now(tz=VIETNAM_TZ)

        try:
            await self.sender.send("🔗 Bạn đã được kết nối! Hãy nhắn tin qua bot.")
            await self.receiver.send("🔗 Bạn đã được kết nối! Hãy nhắn tin qua bot.")
        except discord.Forbidden:
            pass

        await interaction.response.edit_message(content="✅ Bạn đã chấp nhận!", view=None)

    @discord.ui.button(label="Từ chối ❌", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.sender.send("❌ Người kia đã từ chối kết nối.")
        except discord.Forbidden:
            pass
        await interaction.response.edit_message(content="Bạn đã từ chối.", view=None)


class AnonymousChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_sessions = {}       # {user_id: partner_id}
        self.last_message_time = {}     # {(user1, user2): datetime}
        self.check_inactive_sessions.start()

    def cog_unload(self):
        self.check_inactive_sessions.cancel()

    # ===== SLASH COMMAND nhantinan =====
    @app_commands.command(name="nhantinan", description="Kết nối ẩn danh với người khác")
    @app_commands.describe(user="Chọn người bạn muốn nhắn tin ẩn danh")
    async def nhantinan(self, interaction: discord.Interaction, user: discord.User):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng trong server.", ephemeral=True
            )
        if user.bot:
            return await interaction.response.send_message(
                "❌ Không thể nhắn tin với bot.", ephemeral=True
            )
        if interaction.user.id in self.active_sessions or user.id in self.active_sessions:
            return await interaction.response.send_message(
                "⚠️ Một trong 2 bạn đã có phiên chat.", ephemeral=True
            )

        embed = discord.Embed(
            title="📩 Yêu cầu kết nối ẩn danh",
            description="Bạn có đồng ý nhận tin nhắn ẩn danh không?\n\nSử dụng **`/endcall`** để kết thúc trò chuyện.",
            color=discord.Color.blue()
        )
        view = ConfirmView(self, interaction.user, user)
        try:
            await user.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Đã gửi yêu cầu đến {user.mention}", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Không thể gửi DM đến người này.", ephemeral=True
            )

    # ===== SLASH COMMAND endcall =====
    @app_commands.command(name="endcall", description="Kết thúc phiên chat ẩn danh")
    async def endcall(self, interaction: discord.Interaction):
        if interaction.user.id not in self.active_sessions:
            return await interaction.response.send_message(
                "❌ Bạn không có phiên chat.", ephemeral=True
            )

        partner_id = self.active_sessions.pop(interaction.user.id)
        self.active_sessions.pop(partner_id, None)
        key = tuple(sorted([interaction.user.id, partner_id]))
        self.last_message_time.pop(key, None)

        # Gửi interaction response trước
        await interaction.response.send_message("✅ Phiên chat đã kết thúc.", ephemeral=True)

        # Sau đó gửi DM cho cả 2 bên
        try:
            partner = await self.bot.fetch_user(partner_id)
            await partner.send("⚠️ Người kia đã kết thúc phiên chat.")
            await interaction.user.send("⚠️ Bạn đã kết thúc phiên chat.")
        except discord.Forbidden:
            pass

    # ===== RELAY MESSAGES (text, image, video, emoji, sticker) =====
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild and message.author.id in self.active_sessions:
            partner_id = self.active_sessions[message.author.id]
            partner = await self.bot.fetch_user(partner_id)
            key = tuple(sorted([message.author.id, partner_id]))
            self.last_message_time[key] = datetime.now(tz=VIETNAM_TZ)

            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_author(name="💬 Tin nhắn Ẩn danh")
            embed.set_footer(text=f"⏰ {message.created_at.astimezone(VIETNAM_TZ).strftime('%H:%M:%S - %d/%m/%Y')}")

            if message.content:
                embed.description = message.content

            files = []

            # Attachments (image/video)
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith(("image/", "video/")):
                    files.append(await attachment.to_file())

            # Stickers
            for sticker in message.stickers:
                sticker_bytes = await sticker.read()
                files.append(discord.File(fp=sticker_bytes, filename=f"{sticker.name}.png"))

            try:
                await partner.send(embed=embed if embed.description else None, files=files if files else None)
            except:
                await message.author.send("❌ Không thể gửi nội dung đến người kia.")

    # ===== AUTO TIMEOUT =====
    @tasks.loop(minutes=1)
    async def check_inactive_sessions(self):
        now = datetime.now(tz=VIETNAM_TZ)
        timeout = timedelta(minutes=5)
        expired = [k for k, t in self.last_message_time.items() if now - t > timeout]

        for u1, u2 in expired:
            self.active_sessions.pop(u1, None)
            self.active_sessions.pop(u2, None)
            self.last_message_time.pop((u1, u2), None)

            for uid in [u1, u2]:
                try:
                    user = await self.bot.fetch_user(uid)
                    await user.send(f"⏰ Phiên chat đã kết thúc do không hoạt động 5 phút ({now.strftime('%H:%M:%S')})")
                except discord.Forbidden:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousChat(bot))