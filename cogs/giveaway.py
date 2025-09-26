# cogs/giveaway.py
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import random
import pytz
import string
import json
import os
from typing import Optional, List

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
DATA_FILE = "giveaways.json"
COUNTDOWN_INTERVAL = 15  # giây, cập nhật thời gian trên embed

# -------------------- Helpers: load/save --------------------
def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# In-memory mirror of saved data for speed (kept consistent)
RAW = load_data()


def generate_id() -> str:
    return "G-" + "".join(random.choices(string.digits, k=4))


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


# -------------------- Giveaway Model --------------------
class Giveaway:
    def __init__(self, creator_id: int = None, data: dict = None):
        if data:
            # restore
            self.id: str = data["id"]
            self.creator_id: int = data["creator_id"]
            self.reward: str = data["reward"]
            self.days: int = data["days"]
            self.hour: int = data["hour"]
            self.minute: int = data["minute"]
            self.num_winners: int = data["num_winners"]
            self.users: List[int] = data.get("users", [])
            self.channel_id: Optional[int] = data.get("channel_id")
            self.message_id: Optional[int] = data.get("message_id")
            self.end_time_iso: Optional[str] = data.get("end_time")
        else:
            # new
            self.id = generate_id()
            self.creator_id = creator_id
            self.reward = "Chưa đặt"
            self.days = 1
            self.hour = 18
            self.minute = 0
            self.num_winners = 1
            self.users = []
            self.channel_id = None
            self.message_id = None
            self.end_time_iso = None

    @property
    def end_time(self) -> Optional[datetime]:
        if self.end_time_iso:
            try:
                # parse ISO format with tz
                return datetime.fromisoformat(self.end_time_iso)
            except:
                return None
        return None

    @end_time.setter
    def end_time(self, dt: Optional[datetime]):
        if dt:
            # ensure tz-aware ISO
            self.end_time_iso = dt.isoformat()
        else:
            self.end_time_iso = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "reward": self.reward,
            "days": self.days,
            "hour": self.hour,
            "minute": self.minute,
            "num_winners": self.num_winners,
            "users": self.users,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "end_time": self.end_time_iso,
        }

    def build_embed(self, creator: Optional[discord.User] = None, status: str = "🛠️ Setup"):
        # remaining time display
        remaining_text = "Chưa bắt đầu"
        if self.end_time:
            diff = self.end_time - now_vn()
            if diff.total_seconds() <= 0:
                remaining_text = "Đang xử lý..."
            else:
                days = diff.days
                hours, rem = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                parts = []
                if days:
                    parts.append(f"{days}d")
                if hours:
                    parts.append(f"{hours}h")
                if minutes:
                    parts.append(f"{minutes}m")
                parts.append(f"{seconds}s")
                remaining_text = " ".join(parts)

        desc = (
            f"**ID:** `{self.id}`\n"
            f"**Phần thưởng:** {self.reward}\n"
            f"**Số người thắng:** {self.num_winners}\n"
            f"**Kết thúc:** sau {self.days} ngày, lúc {self.hour:02d}:{self.minute:02d} (VN)\n"
            f"**Người tham gia:** {len(self.users)}\n"
            f"**Thời gian còn lại:** {remaining_text}"
        )
        embed = discord.Embed(
            title=f"🎉 Giveaway · {status}",
            description=desc,
            color=discord.Color.blurple(),
            timestamp=now_vn(),
        )
        if creator:
            embed.set_footer(text=f"Tạo bởi {creator}", icon_url=creator.avatar.url if creator and creator.avatar else None)
            try:
                if creator and creator.avatar:
                    embed.set_thumbnail(url=creator.avatar.url)
            except:
                pass
        return embed


# -------------------- Cog --------------------
class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # restore in-memory RAW and restart countdown tasks
        # RAW is already loaded from JSON at import
        for gid, data in list(RAW.items()):
            # schedule countdown only if has end_time
            gw = Giveaway(data=data)
            if gw.end_time:
                # try to re-schedule countdown
                self.bot.loop.create_task(self._ensure_countdown(gw))

    # ---------- Slash: /scgiveaway (create/setup) ----------
    @app_commands.command(name="scgiveaway", description="Tạo giveaway mới (mở menu setup)")
    async def scgiveaway(self, interaction: discord.Interaction):
        # create new giveaway object and persist
        gw = Giveaway(creator_id=interaction.user.id)
        RAW[gw.id] = gw.to_dict()
        save_data(RAW)

        # send setup embed + view
        embed = gw.build_embed(creator=interaction.user, status="🛠️ Setup")
        view = self._build_setup_view(gw)
        msg = await interaction.channel.send(embed=embed, view=view)
        gw.channel_id = msg.channel.id
        gw.message_id = msg.id
        RAW[gw.id] = gw.to_dict()
        save_data(RAW)

        await interaction.response.send_message(f"✅ Giveaway `{gw.id}` đã tạo. Kiểm tra message ở kênh này.", ephemeral=True)

    # ---------- Slash: /scgiveawaycheck <id> (participants) ----------
    @app_commands.command(name="scgiveawaycheck", description="Xem danh sách người tham gia giveaway theo ID")
    @app_commands.describe(giveaway_id="ID giveaway (ví dụ G-1234)")
    async def scgiveawaycheck(self, interaction: discord.Interaction, giveaway_id: str):
        data = RAW.get(giveaway_id)
        if not data:
            await interaction.response.send_message("❌ Không tìm thấy giveaway với ID đó.", ephemeral=True)
            return
        gw = Giveaway(data=data)
        # show first page (page 1)
        await self._respond_participants(interaction, gw, page=1)

    # ---------- Build views: setup & join ----------
    def _build_setup_view(self, gw: Giveaway) -> discord.ui.View:
        v = discord.ui.View(timeout=None)
        gid = gw.id

        # row 1: day +/- , hour modal
        v.add_item(discord.ui.Button(label="+Ngày", style=discord.ButtonStyle.success, custom_id=f"{gid}|plusday"))
        v.add_item(discord.ui.Button(label="-Ngày", style=discord.ButtonStyle.danger, custom_id=f"{gid}|minusday"))
        v.add_item(discord.ui.Button(label="⏰ Chỉnh giờ", style=discord.ButtonStyle.primary, custom_id=f"{gid}|sethour"))

        # row 2: reward modal, winners +/-
        v.add_item(discord.ui.Button(label="🎁 Chỉnh phần thưởng", style=discord.ButtonStyle.secondary, custom_id=f"{gid}|setreward"))
        v.add_item(discord.ui.Button(label="+Winner", style=discord.ButtonStyle.success, custom_id=f"{gid}|pluswin"))
        v.add_item(discord.ui.Button(label="-Winner", style=discord.ButtonStyle.danger, custom_id=f"{gid}|minuswin"))

        # row 3: start / cancel
        v.add_item(discord.ui.Button(label="🚀 Bắt đầu Giveaway", style=discord.ButtonStyle.success, custom_id=f"{gid}|start"))
        v.add_item(discord.ui.Button(label="❌ Huỷ Giveaway", style=discord.ButtonStyle.danger, custom_id=f"{gid}|cancel"))
        return v

    def _build_join_view(self, gw: Giveaway) -> discord.ui.View:
        v = discord.ui.View(timeout=None)
        gid = gw.id
        # Show Join / Leave. We'll control enabled/disabled based on global state:
        joined_any = len(gw.users) > 0  # just a heuristic; we will keep both buttons visible.
        # Join (green)
        v.add_item(discord.ui.Button(label="🎉 Tham gia", style=discord.ButtonStyle.success, custom_id=f"{gid}|join"))
        # Leave (red)
        v.add_item(discord.ui.Button(label="🚪 Rời", style=discord.ButtonStyle.danger, custom_id=f"{gid}|leave"))
        # Also add manual end (for creator)
        v.add_item(discord.ui.Button(label="🛑 Kết thúc (Creator only)", style=discord.ButtonStyle.secondary, custom_id=f"{gid}|forceend"))
        return v

    # ---------- Global interaction handler ----------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # only handle component interactions (buttons)
        if interaction.type != discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id")
        if not cid or "|" not in cid:
            return
        gid, action = cid.split("|", 1)
        data = RAW.get(gid)
        if not data:
            await interaction.response.send_message("❌ Giveaway không tồn tại hoặc đã kết thúc.", ephemeral=True)
            return

        gw = Giveaway(data=data)

        # -------------------------------------------
        # Actions that only creator can do (setup/start/cancel/forceend)
        # join/leave allowed for any user
        if action in ("plusday", "minusday", "sethour", "setreward", "pluswin", "minuswin", "start", "cancel", "forceend"):
            if interaction.user.id != gw.creator_id:
                await interaction.response.send_message("❌ Chỉ người tạo giveaway mới làm được thao tác này.", ephemeral=True)
                return

        # ---------- Setup actions ----------
        # +/- day
        if action == "plusday":
            gw.days = gw.days + 1
            RAW[gw.id] = gw.to_dict(); save_data(RAW)
            await self._edit_message_embed(gw)
            await interaction.response.defer()
            return
        if action == "minusday":
            gw.days = max(0, gw.days - 1)
            RAW[gw.id] = gw.to_dict(); save_data(RAW)
            await self._edit_message_embed(gw)
            await interaction.response.defer()
            return

        # set hour: modal
        if action == "sethour":
            class HourModal(discord.ui.Modal, title="Nhập giờ kết thúc (HH:MM)"):
                time = discord.ui.TextInput(label="Giờ (VN)", placeholder="18:30", max_length=5)
                async def on_submit(self_modal, modal_inter: discord.Interaction):
                    try:
                        h_str = self_modal.time.value.strip()
                        h, m = map(int, h_str.split(":"))
                        if not (0 <= h < 24 and 0 <= m < 60):
                            raise ValueError
                        gw.hour, gw.minute = h, m
                        RAW[gw.id] = gw.to_dict(); save_data(RAW)
                        await self._edit_message_embed(gw)
                        await modal_inter.response.send_message("✅ Đã cập nhật giờ.", ephemeral=True)
                    except Exception:
                        await modal_inter.response.send_message("❌ Giờ không hợp lệ. Dùng định dạng HH:MM (ví dụ 18:30).", ephemeral=True)
            await interaction.response.send_modal(HourModal())
            return

        # set reward modal
        if action == "setreward":
            class RewardModal(discord.ui.Modal, title="Nhập phần thưởng"):
                r = discord.ui.TextInput(label="Phần thưởng", placeholder="Nitro / Giftcard / ...", max_length=200)
                async def on_submit(self_modal, modal_inter: discord.Interaction):
                    gw.reward = self_modal.r.value.strip() or "Chưa đặt"
                    RAW[gw.id] = gw.to_dict(); save_data(RAW)
                    await self._edit_message_embed(gw)
                    await modal_inter.response.send_message("✅ Đã cập nhật phần thưởng.", ephemeral=True)
            await interaction.response.send_modal(RewardModal())
            return

        # winners +/-
        if action == "pluswin":
            gw.num_winners += 1
            RAW[gw.id] = gw.to_dict(); save_data(RAW)
            await self._edit_message_embed(gw)
            await interaction.response.defer()
            return
        if action == "minuswin":
            gw.num_winners = max(1, gw.num_winners - 1)
            RAW[gw.id] = gw.to_dict(); save_data(RAW)
            await self._edit_message_embed(gw)
            await interaction.response.defer()
            return

        # start
        if action == "start":
            # compute end_time based on days + hour/minute in VN timezone
            et = now_vn() + timedelta(days=gw.days)
            et = et.replace(hour=gw.hour, minute=gw.minute, second=0, microsecond=0)
            gw.end_time = et
            RAW[gw.id] = gw.to_dict(); save_data(RAW)
            # edit message to join view & start countdown
            await self._edit_message_embed(gw, status="🔥 Đang diễn ra")
            self.bot.loop.create_task(self._ensure_countdown(gw))
            await interaction.response.send_message(f"🚀 Giveaway `{gw.id}` đã bắt đầu.", ephemeral=True)
            return

        # cancel
        if action == "cancel":
            # edit original message, remove view, delete data
            await self._edit_message_to_cancelled(gw)
            RAW.pop(gw.id, None); save_data(RAW)
            await interaction.response.send_message("❌ Giveaway đã bị huỷ và xóa.", ephemeral=True)
            return

        # force end (creator)
        if action == "forceend":
            await self._end_giveaway(gw, forced=True)
            await interaction.response.send_message(f"🛑 Giveaway `{gw.id}` đã được kết thúc bởi người tạo.", ephemeral=True)
            return

        # ---------- Join / Leave ----------
        if action == "join":
            if interaction.user.id not in gw.users:
                gw.users.append(interaction.user.id)
                RAW[gw.id] = gw.to_dict(); save_data(RAW)
                await self._edit_message_embed(gw, status="🔥 Đang diễn ra")
                await interaction.response.send_message("🎉 Bạn đã tham gia giveaway!", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Bạn đã tham gia rồi.", ephemeral=True)
            return

        if action == "leave":
            if interaction.user.id in gw.users:
                gw.users.remove(interaction.user.id)
                RAW[gw.id] = gw.to_dict(); save_data(RAW)
                await self._edit_message_embed(gw, status="🔥 Đang diễn ra")
                await interaction.response.send_message("🚪 Bạn đã rời giveaway.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Bạn chưa tham gia giveaway.", ephemeral=True)
            return

    # ---------- Helper: edit message embed (setup or running) ----------
    async def _edit_message_embed(self, gw: Giveaway, status: str = "🛠️ Setup"):
        try:
            channel = self.bot.get_channel(gw.channel_id) or await self.bot.fetch_channel(gw.channel_id)
            msg = await channel.fetch_message(gw.message_id)
            creator = await self.bot.fetch_user(gw.creator_id)
            if gw.end_time:
                embed = gw.build_embed(creator=creator, status=status if status else "🔥 Đang diễn ra")
                view = self._build_join_view(gw)
            else:
                embed = gw.build_embed(creator=creator, status=status)
                view = self._build_setup_view(gw)
            await msg.edit(embed=embed, view=view)
        except Exception:
            # ignore (channel/message may be deleted)
            pass

    async def _edit_message_to_cancelled(self, gw: Giveaway):
        try:
            channel = self.bot.get_channel(gw.channel_id) or await self.bot.fetch_channel(gw.channel_id)
            msg = await channel.fetch_message(gw.message_id)
            embed = discord.Embed(title="❌ Giveaway đã bị huỷ", color=discord.Color.red(), timestamp=now_vn())
            await msg.edit(embed=embed, view=None)
        except Exception:
            pass

    # ---------- Countdown & end ----------
    async def _ensure_countdown(self, gw: Giveaway):
        # If GW removed while scheduling, quit
        while True:
            # refresh from RAW to get updates
            raw = RAW.get(gw.id)
            if not raw:
                return
            gw = Giveaway(data=raw)
            et = gw.end_time
            if not et:
                return
            now = now_vn()
            remaining = (et - now).total_seconds()
            if remaining <= 0:
                await self._end_giveaway(gw)
                return
            # update embed countdown on message
            await self._edit_message_embed(gw, status="🔥 Đang diễn ra")
            # sleep shorter when near end to be responsive
            await asyncio.sleep(min(COUNTDOWN_INTERVAL, max(1, remaining)))

    async def _end_giveaway(self, gw: Giveaway, forced: bool = False):
        # snapshot and remove data from RAW & file first (so no race)
        RAW.pop(gw.id, None)
        save_data(RAW)

        # build channel & announce
        try:
            channel = self.bot.get_channel(gw.channel_id) or await self.bot.fetch_channel(gw.channel_id)
        except Exception:
            channel = None

        if not gw.users:
            if channel:
                await channel.send(f"❌ Giveaway `{gw.id}` kết thúc nhưng không có người tham gia.")
            return

        winners = random.sample(gw.users, min(len(gw.users), gw.num_winners))
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        # Send public result embed
        public_embed = discord.Embed(
            title="🎊 Giveaway Kết Thúc!",
            description=f"**Phần thưởng:** {gw.reward}\n**Người thắng:** {mentions}",
            color=discord.Color.gold(),
            timestamp=now_vn()
        )
        # set thumbnail as creator avatar if possible
        try:
            creator = await self.bot.fetch_user(gw.creator_id)
            if creator and creator.avatar:
                public_embed.set_footer(text=f"Tạo bởi {creator}", icon_url=creator.avatar.url)
        except:
            creator = None

        if channel:
            await channel.send(embed=public_embed)

        # DM each winner with embed showing winner avatar + creator info
        for uid in winners:
            try:
                user = await self.bot.fetch_user(uid)
                # build DM embed
                dm_embed = discord.Embed(
                    title="🎉 Chúc mừng! Bạn đã thắng Giveaway",
                    description=f"**Phần thưởng:** {gw.reward}\n**ID Giveaway:** `{gw.id}`",
                    color=discord.Color.green(),
                    timestamp=now_vn()
                )
                # set winner avatar as thumbnail (if available)
                try:
                    if user.avatar:
                        dm_embed.set_thumbnail(url=user.avatar.url)
                except:
                    pass
                # show creator info in embed field (with avatar url if possible)
                if creator:
                    creator_name = getattr(creator, "display_name", str(creator))
                    dm_embed.add_field(name="Tạo bởi", value=f"{creator_name}", inline=True)
                    try:
                        if creator.avatar:
                            dm_embed.set_footer(text=f"Tạo bởi {creator_name}", icon_url=creator.avatar.url)
                    except:
                        pass
                # open DM and send embed
                try:
                    await user.send(embed=dm_embed)
                except Exception:
                    # can't DM — ignore
                    pass
            except Exception:
                continue

        # try to edit original message view to removed/ended state
        try:
            if channel:
                msg = await channel.fetch_message(gw.message_id)
                ended_embed = discord.Embed(
                    title="🎊 Giveaway Đã Kết Thúc",
                    description=f"**Phần thưởng:** {gw.reward}\n**Người thắng:** {mentions}",
                    color=discord.Color.gold(),
                    timestamp=now_vn()
                )
                await msg.edit(embed=ended_embed, view=None)
        except:
            pass

        # finally delete local store for this id (already removed)
        # participants list is no longer stored in RAW (deleted above)

    # ---------- Participants command internals (pagination) ----------
    async def _respond_participants(self, interaction: discord.Interaction, gw: Giveaway, page: int = 1):
        users = gw.users or []
        per_page = 25
        max_page = (len(users) - 1) // per_page + 1 if users else 1
        page = max(1, min(page, max_page))
        start = (page - 1) * per_page
        end = start + per_page
        page_users = users[start:end]

        lines = []
        for idx, uid in enumerate(page_users, start=start + 1):
            lines.append(f"{idx}. <@{uid}> (`{uid}`)")

        desc = "\n".join(lines) if lines else "Không có người tham gia."
        embed = discord.Embed(
            title=f"📋 Participants · {gw.id} (Trang {page}/{max_page})",
            description=desc,
            color=discord.Color.blurple(),
            timestamp=now_vn()
        )
        # show basic meta
        try:
            creator = await self.bot.fetch_user(gw.creator_id)
            embed.set_footer(text=f"Tạo bởi {creator}", icon_url=creator.avatar.url if creator and creator.avatar else None)
        except:
            pass

        # Build view with Prev/Next that include page number
        view = discord.ui.View(timeout=120)
        if page > 1:
            view.add_item(discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, custom_id=f"{gw.id}|participants|{page-1}"))
        if page < max_page:
            view.add_item(discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id=f"{gw.id}|participants|{page+1}"))

        # Reply ephemeral so only the requester sees it
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # listen for participants pagination button clicks
    @commands.Cog.listener()
    async def on_interaction_component(self, interaction: discord.Interaction):
        # Some libraries may not call this — fallback to on_interaction above handles most
        # But implement for the custom_id pattern used in participants view:
        if interaction.type != discord.InteractionType.component:
            return
        cid = interaction.data.get("custom_id")
        if not cid:
            return
        parts = cid.split("|")
        if len(parts) == 3 and parts[1] == "participants":
            gid = parts[0]
            page = int(parts[2])
            data = RAW.get(gid)
            if not data:
                await interaction.response.send_message("❌ Giveaway không tồn tại.", ephemeral=True)
                return
            gw = Giveaway(data=data)
            await self._respond_participants(interaction, gw, page=page)
            return

    # ---------- Cog unload/save ----------
    def cog_unload(self):
        # save RAW just in case
        save_data(RAW)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))