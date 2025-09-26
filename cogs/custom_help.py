import discord
from discord.ext import commands
from discord import app_commands

ADMIN_ID = 660507549442900009  # ID của bạn


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="schelp", description="Hiển thị hướng dẫn sử dụng bot")
    async def schelp(self, interaction: discord.Interaction):
        # Embed cho Member
        member_embed = discord.Embed(
            title="📖 Hướng dẫn sử dụng bot - Thành viên",
            color=discord.Color.gold()
        )
        member_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        member_embed.add_field(
            name="💬 Anonymous Chat",
            value="`/nhantinan <user>` - Gửi lời mời chat ẩn danh\n"
                  "`/endcall` - Kết thúc phiên chat",
            inline=False
        )

        member_embed.add_field(
            name="🎉 Giveaway",
            value="`/scgiveaway` - Tạo giveaway mới và mở menu setup\n"
                  "`/scgiveawaycheck <ID>` - Xem danh sách người tham gia giveaway theo ID",
            inline=False
        )

        member_embed.add_field(
            name="📊 Tracking",
            value="Theo dõi **Mute/Gỡ Mute, Role, Kick, Ban, Unban** và gửi log cho Admin",
            inline=False
        )

        member_embed.add_field(
            name="⚔️ Game RPG",
            value="`/start` - Tạo nhân vật và chọn class\n"
                  "`/profile` - Xem thông tin nhân vật\n"
                  "`/inventory` - Xem túi đồ\n"
                  "`/trade @user` - Trao đổi vật phẩm với người khác\n"
                  "`/clan` - Quản lý clan (tạo, tham gia, rời, xem thông tin)",
            inline=False
        )

        member_embed.add_field(
            name="🔎 Check User",
            value="`sc?check [@user]` - Xem thông tin cơ bản của một user\n"
                  "*(Admin bot sẽ thấy chi tiết hơn)*",
            inline=False
        )

        member_embed.set_footer(
            text=f"Được gọi bởi {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        # Embed cho Admin (chỉ bạn mới xem được)
        admin_embed = discord.Embed(
            title="🛡 Hướng dẫn sử dụng bot - Admin Bot",
            color=discord.Color.red()
        )
        admin_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        admin_embed.add_field(
            name="🔧 Admin Commands",
            value="`sc?status` - Đổi trạng thái bot\n"
                  "`sc?owner` - Menu quản trị Admin Bot (Reset DB, Thống kê, Test, ...)",
            inline=False
        )
        admin_embed.set_footer(
            text=f"Chỉ Admin Bot có thể xem",
            icon_url=interaction.user.display_avatar.url
        )

        # Nếu là Admin thì cho phép chuyển trang, còn không thì chỉ gửi trang Member
        if interaction.user.id == ADMIN_ID:
            view = HelpView(member_embed, admin_embed)
            await interaction.response.send_message(embed=member_embed, view=view, ephemeral=False)
        else:
            await interaction.response.send_message(embed=member_embed, ephemeral=False)


class HelpView(discord.ui.View):
    def __init__(self, member_embed, admin_embed):
        super().__init__(timeout=120)
        self.member_embed = member_embed
        self.admin_embed = admin_embed
        self.current_page = 0  # 0 = member, 1 = admin

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Chỉ Admin Bot mới dùng được.", ephemeral=True)

        self.current_page = 0
        await interaction.response.edit_message(embed=self.member_embed, view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Chỉ Admin Bot mới dùng được.", ephemeral=True)

        self.current_page = 1
        await interaction.response.edit_message(embed=self.admin_embed, view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))