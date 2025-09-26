import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from datetime import timedelta

# ⚙️ Config
restrict_mode = False
allowed_id = 660507549442900009  # Owner chính
allowed_id_moderator = [660507549442900009, 416613894887440384]  # danh sách mod
verified_users = [660507549442900009, 416613894887440384]

# 🔇 Modal nhập thời gian mute
class MuteModal(Modal, title="🔇 Nhập thời gian mute"):
    duration = TextInput(label="Thời gian mute (phút)", placeholder="Ví dụ: 10", required=True)

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
            until = discord.utils.utcnow() + timedelta(minutes=minutes)
            await self.member.timeout(until, reason=f"Bị hạn chế bởi {interaction.user}")

            await interaction.response.send_message(
                f"✅ {self.member.mention} đã bị hạn chế trong {minutes} phút.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: {e}", ephemeral=True)


# 🎛️ View Kick / Ban / Mute
class UserInfoView(View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        self.member = member

    @discord.ui.button(label="⚠️ Kick", style=discord.ButtonStyle.danger)
    async def kick(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in allowed_id_moderator:
            return await interaction.response.send_message("❌ Bạn không có quyền Kick.", ephemeral=True)

        await self.member.kick(reason=f"Kick bởi {interaction.user}")
        await interaction.response.send_message(f"✅ {self.member.mention} đã bị kick.", ephemeral=True)

    @discord.ui.button(label="⛔ Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in allowed_id_moderator:
            return await interaction.response.send_message("❌ Bạn không có quyền Ban.", ephemeral=True)

        await self.member.ban(reason=f"Ban bởi {interaction.user}")
        await interaction.response.send_message(f"✅ {self.member.mention} đã bị ban.", ephemeral=True)

    @discord.ui.button(label="🔇 Hạn chế", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in allowed_id_moderator:
            return await interaction.response.send_message("❌ Bạn không có quyền Hạn chế.", ephemeral=True)

        await interaction.response.send_modal(MuteModal(self.member))


def is_moderator(ctx):
    return ctx.author.id in allowed_id_moderator


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ⚙️ Restrict Mode ON/OFF
    @commands.command()
    async def setting(self, ctx, mode: str = None):
        global restrict_mode
        if ctx.author.id != allowed_id:
            return await ctx.send("❌ Bạn không có quyền thay đổi chế độ.")

        if mode is None:
            return await ctx.send(f"⚙️ Restrict hiện tại: {'ON' if restrict_mode else 'OFF'}")

        if mode.lower() == "on":
            restrict_mode = True
            await ctx.send(f"✅ Đã bật chế độ chỉ cho phép <@{allowed_id}> dùng lệnh.")
        elif mode.lower() == "off":
            restrict_mode = False
            await ctx.send("✅ Đã tắt chế độ, ai cũng có thể dùng lệnh.")
        else:
            await ctx.send("❌ Sai cú pháp. Dùng `sc?setting on` hoặc `sc?setting off`.")

    # 📌 Lệnh check thông tin user
    @commands.command()
    async def check(self, ctx, member: discord.Member = None):
        global restrict_mode, allowed_id

        if restrict_mode and ctx.author.id != allowed_id:
            return await ctx.send("❌ Bạn không có quyền dùng lệnh này.")

        member = member or ctx.author
        verified = " ✅" if member.id in verified_users else ""

        embed = discord.Embed(
            title=f"Thông tin của {member.display_name}{verified}",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="👤 Username", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="📅 Tham gia Discord", value=discord.utils.format_dt(member.created_at, 'F'), inline=False)
        embed.add_field(name="📌 Tham gia server", value=discord.utils.format_dt(member.joined_at, 'F'), inline=False)

        roles = " ".join([role.mention for role in member.roles if role != ctx.guild.default_role])
        embed.add_field(name="🎭 Roles", value=roles if roles else "Không có role", inline=False)

        view = UserInfoView(member)
        await ctx.send(embed=embed, view=view)

    # ✅ Add Verified
    @commands.command()
    async def addtick(self, ctx, user: discord.User):
        if not is_moderator(ctx):
            return await ctx.send("❌ Bạn không có quyền thêm verified user.")
        if user.id in verified_users:
            return await ctx.send(f"⚠️ <@{user.id}> đã có verified.")
        verified_users.append(user.id)
        await ctx.send(f"✅ Đã thêm <@{user.id}> vào verified users.")

    # 📋 Check Verified
    @commands.command()
    async def checktick(self, ctx):
        if not is_moderator(ctx):
            return await ctx.send("❌ Bạn không có quyền xem danh sách verified.")
        if not verified_users:
            return await ctx.send("📭 Chưa có verified user nào.")

        embed = discord.Embed(title="📋 Danh sách Verified Users", color=discord.Color.green())
        for uid in verified_users:
            try:
                user = await self.bot.fetch_user(uid)
                embed.add_field(name=user.name, value=f"✅ <@{uid}>", inline=False)
            except:
                embed.add_field(name="Người dùng không tồn tại", value=f"ID: {uid}", inline=False)

        await ctx.send(embed=embed)

    # 🗑️ Xóa Verified
    @commands.command()
    async def xoatick(self, ctx, user: discord.User):
        if not is_moderator(ctx):
            return await ctx.send("❌ Bạn không có quyền xoá verified user.")
        if user.id not in verified_users:
            return await ctx.send(f"⚠️ <@{user.id}> không có trong danh sách verified.")
        verified_users.remove(user.id)
        await ctx.send(f"🗑️ Đã xoá <@{user.id}> khỏi verified users.")


async def setup(bot):
    await bot.add_cog(Moderation(bot))