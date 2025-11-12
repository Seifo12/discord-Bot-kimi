import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select, Modal
import asyncio
import random
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# ====================== تحميل متغيرات البيئة ======================
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ خطأ: لم يتم العثور على التوكن!")
    print("📝 تأكد من إنشاء ملف .env يحتوي على:")
    print("DISCORD_TOKEN=توكن_البوت_هنا")
    exit()

# ====================== إعدادات البوت ======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# الألوان الثابتة
SUCCESS_COLOR = 0x2ECC71
ERROR_COLOR = 0xE74C3C
WARN_COLOR = 0xF1C40F
INFO_COLOR = 0x3498DB
MAIN_COLOR = 0x9B59B6

# قاعدة البيانات
DATABASE_FILE = "database.json"
tickets_db = {}
tickets_by_channel = {}
warnings_db = {}
levels_db = {}
economy_db = {}

def load_data():
    global warnings_db, levels_db, economy_db
    try:
        with open(DATABASE_FILE, 'r') as f:
            data = json.load(f)
            warnings_db = data.get("warnings", {})
            levels_db = data.get("levels", {})
            economy_db = data.get("economy", {})
            print("✅ تم تحميل البيانات بنجاح.")
    except FileNotFoundError:
        print("⚠️ ملف البيانات غير موجود، سيتم إنشاء ملف جديد عند الحفظ.")
    except json.JSONDecodeError:
        print("❌ خطأ في قراءة ملف البيانات، قد يكون تالفاً.")

def save_data():
    with open(DATABASE_FILE, 'w') as f:
        data_to_save = {
            "warnings": warnings_db,
            "levels": levels_db,
            "economy": economy_db
        }
        json.dump(data_to_save, f, indent=4)

# ====================== الرتب والقنوات ======================
ROLES = [
    {"name": "👑 • المالك", "color": 0xFF0000, "permissions": discord.Permissions.all()},
    {"name": "🔮 • المالك المشارك", "color": 0x9B59B6, "permissions": discord.Permissions.all()},
    {"name": "⚔️ • الإدارة", "color": 0x3498DB, "permissions": discord.Permissions(administrator=True)},
    {"name": "🛡️ • المشرف", "color": 0x2ECC71, "permissions": discord.Permissions(
        kick_members=True, ban_members=True, manage_messages=True,
        manage_channels=True, mute_members=True, deafen_members=True
    )},
    {"name": "🎯 • المساعد", "color": 0xF1C40F, "permissions": discord.Permissions(
        kick_members=True, manage_messages=True, mute_members=True
    )},
    {"name": "💎 • البوستر", "color": 0xE91E63, "permissions": discord.Permissions.none()},
    {"name": "🏆 • الرائع", "color": 0xE67E22, "permissions": discord.Permissions.none()},
    {"name": "👤 • العضو", "color": 0x95A5A6, "permissions": discord.Permissions.none()},
]

ROLE_HIERARCHY = [role["name"] for role in ROLES]

CATEGORIES_AND_CHANNELS = {
    "📢 • الإعلانات": ["📣・الإعلانات-الرسمية", "📰・الأخبار", "🎉・الفعاليات", "🎁・الهدايا"],
    "💬 • الدردشة": ["💭・الدردشة-العامة", "🎮・الألعاب", "🎨・الفن-والإبداع", "📷・الصور-والميمز", "🤖・أوامر-البوت"],
    "🎵 • الصوتيات": ["🔊・الروم-العام", "🎵・الموسيقى", "🎮・الجيمنج-1", "🎮・الجيمنج-2", "🎤・البودكاست"],
    "🎫 • الدعم الفني": ["🎫・إنشاء-تذكرة", "📋・التذاكر-المفتوحة"],
    "⚙️ • الإدارة": ["🛠️・إدارة-السيرفر", "📊・السجلات", "⚠️・البلاغات", "🚨・التحذيرات"],
    "ℹ️ • المعلومات": ["📜・القوانين", "👋・الترحيب", "📌・الروابط-المهمة", "📊・الإحصائيات"]
}

# ====================== نظام التذاكر ======================
class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="دعم فني", description="مشاكل تقنية وأسئلة حول البوت", emoji="💻", value="tech_support"),
            discord.SelectOption(label="مشكلة بالسيرفر", description="مشاكل متعلقة بإعدادات السيرفر", emoji="⚙️", value="server_problem"),
            discord.SelectOption(label="شكوى على عضو/إداري", description="للشكاوى ضد الأعضاء أو فريق العمل", emoji="⚖️", value="complaint")
        ]
        super().__init__(placeholder="🎫 اختر نوع التذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_type_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        ticket_type = self.values[0]

        if str(member.id) in tickets_db and any(ch.id == tickets_db[str(member.id)]["channel_id"] for ch in guild.channels):
            await interaction.response.send_message("❌ لديك تذكرة مفتوحة بالفعل!", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="🎫 • الدعم الفني")
        if not category:
            await interaction.response.send_message("❌ لا يمكن العثور على قسم الدعم الفني.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        admin_role = discord.utils.get(guild.roles, name="⚔️ • الإدارة")
        mod_role = discord.utils.get(guild.roles, name="🛡️ • المشرف")
        coowner_role = discord.utils.get(guild.roles, name="🔮 • المالك المشارك")

        if admin_role: overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if mod_role: overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(f"🎫┃{member.name}", category=category, overwrites=overwrites)

        ticket_data = {"channel_id": ticket_channel.id, "type": ticket_type, "accepted_by": None, "owner_id": str(member.id)}
        tickets_db[str(member.id)] = ticket_data
        tickets_by_channel[ticket_channel.id] = ticket_data

        type_names = {"tech_support": "💻 دعم فني", "server_problem": "⚙️ مشكلة بالسيرفر", "complaint": "⚖️ شكوى"}

        terms_embed = discord.Embed(title="📜 قواعد وشروط التذاكر", description="• يُمنع المنشن غير الضروري.\n• شرح المشكلة بوضوح واختصار.\n• احترام فريق الدعم.", color=WARN_COLOR)
        embed = discord.Embed(title=f"🎫 تذكرة جديدة: {type_names[ticket_type]}", description=f"مرحباً {member.mention}،\n\nالرجاء الانتظار، سيقوم أحد أعضاء فريق الدعم بالرد عليك قريباً.", color=SUCCESS_COLOR)
        embed.set_footer(text=f"ID: {member.id}")

        mention_text = ""
        if ticket_type == "complaint" and coowner_role:
            mention_text = f"{coowner_role.mention}"
        elif admin_role:
            mention_text = f"{admin_role.mention}"

        await ticket_channel.send(content=mention_text, embeds=[terms_embed, embed], view=TicketManagementView(ticket_channel.id))
        await interaction.response.send_message(f"✅ تم إنشاء تذكرتك في {ticket_channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

class RenameModal(Modal, title="إعادة تسمية التذكرة"):
    new_name = discord.ui.TextInput(label="الاسم الجديد", placeholder="أدخل اسم القناة الجديد...", required=True, max_length=100)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.channel.edit(name=self.new_name.value)
            await interaction.response.send_message(f"✅ تم تغيير اسم القناة إلى: **{self.new_name.value}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ خطأ: {e}", ephemeral=True)

class TicketManagementView(View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⏳ جاري إغلاق التذكرة خلال 5 ثواني...", ephemeral=True)
        
        owner_id = tickets_by_channel.get(self.channel_id, {}).get("owner_id")
        if owner_id and owner_id in tickets_db:
            del tickets_db[owner_id]
        if self.channel_id in tickets_by_channel:
            del tickets_by_channel[self.channel_id]
        
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"أغلق بواسطة {interaction.user}")
        except discord.NotFound:
            pass

    @discord.ui.button(label="🗑️ حذف فوري", style=discord.ButtonStyle.grey, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: Button):
        high_staff = ["👑 • المالك", "🔮 • المالك المشارك", "⚔️ • الإدارة"]
        user_roles = [role.name for role in interaction.user.roles]
        if not any(role in high_staff for role in user_roles):
            await interaction.response.send_message("❌ هذه الصلاحية للإدارة العليا فقط.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ سيتم حذف القناة فوراً.", ephemeral=True)
        
        owner_id = tickets_by_channel.get(self.channel_id, {}).get("owner_id")
        if owner_id and owner_id in tickets_db:
            del tickets_db[owner_id]
        if self.channel_id in tickets_by_channel:
            del tickets_by_channel[self.channel_id]

        try:
            await interaction.channel.delete(reason=f"حذف فوري بواسطة {interaction.user}")
        except discord.NotFound:
            pass

# ==================== نظام المستويات والاقتصاد ====================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    user_id = str(message.author.id)
    
    # نظام المستويات
    if user_id not in levels_db:
        levels_db[user_id] = {"xp": 0, "level": 1, "messages": 0}
    
    levels_db[user_id]["messages"] += 1
    levels_db[user_id]["xp"] += random.randint(5, 15)
    
    xp = levels_db[user_id]["xp"]
    level = levels_db[user_id]["level"]
    xp_needed = level * 100 + (level * 25)
    
    if xp >= xp_needed:
        levels_db[user_id]["level"] += 1
        levels_db[user_id]["xp"] = 0
        new_level = levels_db[user_id]["level"]
        
        embed = discord.Embed(title="🎉 ترقية مستوى!", description=f"مبروك {message.author.mention}، لقد وصلت للمستوى **{new_level}**!", color=0xFFD700)
        await message.channel.send(embed=embed, delete_after=15)
    
    # نظام الاقتصاد
    if user_id not in economy_db:
        economy_db[user_id] = {"coins": 0, "bank": 0, "last_daily": None}
    economy_db[user_id]["coins"] += random.randint(1, 3)
    
    if random.randint(1, 100) == 1:
        save_data()

    await bot.process_commands(message)

# ==================== Slash Commands ====================

@bot.tree.command(name="مستوى", description="عرض مستوى العضو وخبرته")
@app_commands.describe(member="العضو الذي تريد عرض مستواه")
async def level_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    user_id = str(member.id)
    
    data = levels_db.get(user_id, {"xp": 0, "level": 1, "messages": 0})
    xp_needed = data["level"] * 100 + (data["level"] * 25)
    
    progress = int((data['xp'] / xp_needed) * 20) if xp_needed > 0 else 0
    progress_bar = '🟩' * progress + '⬛' * (20 - progress)

    embed = discord.Embed(title=f"📊 مستوى {member.display_name}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="المستوى", value=f"🏆 {data['level']}", inline=True)
    embed.add_field(name="الرسائل", value=f"💬 {data['messages']}", inline=True)
    embed.add_field(name="الخبرة", value=f"⭐ {data['xp']} / {xp_needed}", inline=True)
    embed.add_field(name="التقدم نحو المستوى التالي", value=f"`{progress_bar}`", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ترتيب", description="عرض قائمة المتصدرين في المستويات")
async def leaderboard_slash(interaction: discord.Interaction):
    sorted_users = sorted(levels_db.items(), key=lambda item: (item[1]['level'], item[1]['xp']), reverse=True)[:10]
    
    embed = discord.Embed(title="🏆 لوحة المتصدرين", description="أعلى 10 أعضاء في السيرفر", color=0xFFD700)
    
    for idx, (user_id, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(user_id))
        if member:
            embed.add_field(name=f"#{idx} - {member.display_name}", value=f"**المستوى:** {data['level']} | **الخبرة:** {data['xp']}", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="يومي", description="الحصول على المكافأة اليومية")
async def daily_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    user_data = economy_db.get(user_id, {"coins": 0, "bank": 0, "last_daily": None})
    last_daily_str = user_data.get("last_daily")
    
    if last_daily_str:
        last_daily = datetime.fromisoformat(last_daily_str)
        if datetime.now() - last_daily < timedelta(hours=23, minutes=30):
            await interaction.response.send_message("❌ لقد حصلت على مكافأتك بالفعل، عد غداً!", ephemeral=True)
            return
            
    reward = random.randint(200, 750)
    user_data["coins"] = user_data.get("coins", 0) + reward
    user_data["last_daily"] = datetime.now().isoformat()
    economy_db[user_id] = user_data
    save_data()
    
    embed = discord.Embed(title="🎁 مكافأة يومية!", description=f"لقد حصلت على **{reward}** 🪙!", color=SUCCESS_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="رصيد", description="عرض رصيدك")
@app_commands.describe(member="العضو")
async def balance_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    user_id = str(member.id)
    data = economy_db.get(user_id, {"coins": 0, "bank": 0, "last_daily": None})
    
    embed = discord.Embed(title=f"💰 رصيد {member.display_name}", color=SUCCESS_COLOR)
    embed.add_field(name="🪙 النقود", value=f"{data['coins']:,}", inline=True)
    embed.add_field(name="🏦 البنك", value=f"{data['bank']:,}", inline=True)
    embed.add_field(name="📊 الإجمالي", value=f"{data['coins'] + data['bank']:,}", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# ==================== أوامر الإدارة ====================

def get_role_rank(role_name):
    return ROLE_HIERARCHY.index(role_name) if role_name in ROLE_HIERARCHY else 999

def get_highest_staff_role(user_roles):
    highest_rank = 999
    highest_role_name = None
    for role in user_roles:
        rank = get_role_rank(role.name)
        if rank < highest_rank:
            highest_rank = rank
            highest_role_name = role.name
    return highest_role_name, highest_rank

@bot.tree.command(name="اعطاء", description="إعطاء رتبة لعضو مع استبدال الرتبة القديمة")
@app_commands.describe(member="العضو", role="الرتبة الجديدة")
@app_commands.checks.has_permissions(manage_roles=True)
async def give_role_slash(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if member.bot:
        await interaction.response.send_message("❌ لا يمكن إعطاء رتب للبوتات.", ephemeral=True)
        return
        
    user_highest_role_name, user_rank = get_highest_staff_role(interaction.user.roles)
    target_role_rank = get_role_rank(role.name)

    if user_rank == 999 and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ليس لديك صلاحية إعطاء رتب إدارية!", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator and target_role_rank <= user_rank:
        await interaction.response.send_message("❌ لا يمكنك إعطاء رتبة أعلى من رتبتك أو مساوية لها.", ephemeral=True)
        return
    
    if role.name not in ROLE_HIERARCHY:
        await interaction.response.send_message("⚠️ هذه الرتبة ليست ضمن النظام الهرمي، سيتم إضافتها كرتبة عادية.", ephemeral=True)
        await member.add_roles(role)
        await interaction.followup.send(f"✅ تم إعطاء {member.mention} رتبة {role.mention} (خارج النظام الهرمي).")
        return

    roles_to_remove = [r for r in member.roles if r.name in ROLE_HIERARCHY]
    removed_roles_names = [r.mention for r in roles_to_remove]

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"تغيير الرتبة بواسطة {interaction.user}")
        
        await member.add_roles(role, reason=f"إعطاء رتبة بواسطة {interaction.user}")

        embed = discord.Embed(title="✅ تم تحديث الرتبة بنجاح", color=SUCCESS_COLOR)
        embed.description = f"تم تحديث رتبة {member.mention}."
        embed.add_field(name="➕ الرتبة الجديدة", value=role.mention, inline=False)
        if removed_roles_names:
            embed.add_field(name="➖ الرتب المحذوفة", value=" ".join(removed_roles_names), inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message("❌ خطأ: ليس لدي الصلاحيات الكافية لتعديل رتب هذا العضو. (قد تكون رتبته أعلى من رتبة البوت)", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ غير متوقع: {e}", ephemeral=True)

@bot.tree.command(name="طرد", description="طرد عضو من السيرفر")
@app_commands.describe(member="العضو", reason="سبب الطرد")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member.bot:
        await interaction.response.send_message("❌ لا يمكن طرد البوتات.", ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك طرد شخص برتبة أعلى منك.", ephemeral=True)
        return
    
    if member.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ لا يمكن طرد هذا العضو لأن رتبته أعلى من رتبة البوت.", ephemeral=True)
        return
    
    try:
        await member.kick(reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}")
        
        embed = discord.Embed(title="✅ تم الطرد", description=f"تم طرد {member.mention} بنجاح", color=ERROR_COLOR)
        if reason:
            embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title="🚫 تم طردك", description=f"لقد تم طردك من سيرفر **{interaction.guild.name}**", color=ERROR_COLOR)
            if reason:
                dm_embed.add_field(name="السبب", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
    except Exception as e:
        await interaction.response.send_message(f"❌ فشل الطرد: {e}", ephemeral=True)

@bot.tree.command(name="حظر", description="حظر عضو من السيرفر")
@app_commands.describe(member="العضو", reason="سبب الحظر", delete_days="عدد أيام حذف الرسائل (0-7)")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None, delete_days: int = 0):
    if delete_days < 0 or delete_days > 7:
        await interaction.response.send_message("❌ عدد الأيام يجب أن يكون بين 0 و 7.", ephemeral=True)
        return
    
    if member.bot:
        await interaction.response.send_message("❌ لا يمكن حظر البوتات.", ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك حظر شخص برتبة أعلى منك.", ephemeral=True)
        return
    
    if member.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ لا يمكن حظر هذا العضو لأن رتبته أعلى من رتبة البوت.", ephemeral=True)
        return
    
    try:
        await member.ban(reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}", delete_message_seconds=delete_days*86400)
        
        embed = discord.Embed(title="✅ تم الحظر", description=f"تم حظر {member.mention} بنجاح", color=ERROR_COLOR)
        embed.add_field(name="حذف الرسائل", value=f"آخر {delete_days} أيام", inline=True)
        if reason:
            embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title="⛔ تم حظرك", description=f"لقد تم حظرك من سيرفر **{interaction.guild.name}**", color=ERROR_COLOR)
            if reason:
                dm_embed.add_field(name="السبب", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
    except Exception as e:
        await interaction.response.send_message(f"❌ فشل الحظر: {e}", ephemeral=True)

@bot.tree.command(name="فك_حظر", description="فك حظر عضو")
@app_commands.describe(user_id="معرف العضو (ID)", reason="سبب فك الحظر")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = None):
    try:
        user_id_int = int(user_id)
    except:
        await interaction.response.send_message("❌ معرف المستخدم غير صالح.", ephemeral=True)
        return
    
    try:
        banned_users = [ban async for ban in interaction.guild.bans()]
        target_ban = next((ban for ban in banned_users if ban.user.id == user_id_int), None)
        
        if not target_ban:
            await interaction.response.send_message("❌ هذا المستخدم غير محظور.", ephemeral=True)
            return
        
        await interaction.guild.unban(target_ban.user, reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}")
        
        embed = discord.Embed(title="✅ تم فك الحظر", description=f"تم فك حظر {target_ban.user.mention}", color=SUCCESS_COLOR)
        if reason:
            embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ فشل فك الحظر: {e}", ephemeral=True)

@bot.tree.command(name="مسح", description="مسح عدد معين من الرسائل")
@app_commands.describe(amount="عدد الرسائل", member="مسح رسائل عضو معين فقط")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_slash(interaction: discord.Interaction, amount: int, member: discord.Member = None):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ يجب أن يكون العدد بين 1 و 100.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        if member:
            def check(msg):
                return msg.author.id == member.id
            deleted = await interaction.channel.purge(limit=amount, check=check)
        else:
            deleted = await interaction.channel.purge(limit=amount)
        
        embed = discord.Embed(title="✅ تم المسح", description=f"تم مسح {len(deleted)} رسالة", color=SUCCESS_COLOR)
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        await asyncio.sleep(5)
        await interaction.delete_original_response()
        
    except Exception as e:
        await interaction.followup.send(f"❌ فشل المسح: {e}", ephemeral=True)

@bot.tree.command(name="سرعة", description="تعيين وضع الكتابة البطيء في القناة")
@app_commands.describe(seconds="عدد الثواني (0 لتعطيل)")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode_slash(interaction: discord.Interaction, seconds: int):
    if seconds < 0 or seconds > 21600:
        await interaction.response.send_message("❌ يجب أن يكون العدد بين 0 و 21600 (6 ساعات).", ephemeral=True)
        return
    
    try:
        await interaction.channel.edit(slowmode_delay=seconds)
        
        if seconds == 0:
            embed = discord.Embed(title="✅ تم تعطيل وضع الكتابة البطيء", color=SUCCESS_COLOR)
        else:
            embed = discord.Embed(title="✅ تم تفعيل وضع الكتابة البطيء", description=f"يجب الانتظار {seconds} ثانية بين كل رسالة", color=SUCCESS_COLOR)
        
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ فشل التحديث: {e}", ephemeral=True)

@bot.tree.command(name="تحذير", description="إعطاء تحذير لعضو")
@app_commands.describe(member="العضو", reason="سبب التحذير")
@app_commands.checks.has_permissions(kick_members=True)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member.bot:
        await interaction.response.send_message("❌ لا يمكن إعطاء تحذير للبوتات.", ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك تحذير شخص برتبة أعلى منك.", ephemeral=True)
        return
    
    user_id = str(member.id)
    if user_id not in warnings_db:
        warnings_db[user_id] = []
    
    warn_id = len(warnings_db[user_id]) + 1
    warnings_db[user_id].append({
        "id": warn_id,
        "reason": reason or "لم يحدد سبب",
        "moderator": str(interaction.user.id),
        "timestamp": datetime.now().isoformat()
    })
    
    save_data()
    
    try:
        dm_embed = discord.Embed(title="⚠️ تلقيت تحذيراً", description=f"لقد تلقيت تحذيراً في سيرفر **{interaction.guild.name}**", color=WARN_COLOR)
        dm_embed.add_field(name="المشرف", value=interaction.user.mention, inline=False)
        if reason:
            dm_embed.add_field(name="السبب", value=reason, inline=False)
        await member.send(embed=dm_embed)
    except:
        pass
    
    total_warns = len(warnings_db[user_id])
    max_warns = 3
    
    embed = discord.Embed(title="⚠️ تم إعطاء تحذير", color=WARN_COLOR)
    embed.description = f"تم إعطاء تحذير لـ {member.mention}"
    embed.add_field(name="عدد التحذيرات", value=f"{total_warns}/{max_warns}", inline=True)
    if reason:
        embed.add_field(name="السبب", value=reason, inline=False)
    
    if total_warns >= max_warns:
        try:
            await member.kick(reason=f"تم طرده تلقائياً بعد {max_warns} تحذيرات")
            embed.add_field(name="🚫 إجراء تلقائي", value=f"تم طرد {member.mention} تلقائياً.", inline=False)
        except:
            embed.add_field(name="❌ فشل الإجراء", value="فشل طرد العضو (قد تكون رتبته أعلى من البوت)", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="تحذيرات", description="عرض تحذيرات عضو")
@app_commands.describe(member="العضو")
async def warnings_slash(interaction: discord.Interaction, member: discord.Member):
    user_id = str(member.id)
    if user_id not in warnings_db or not warnings_db[user_id]:
        await interaction.response.send_message(f"✅ {member.mention} ليس لديه أي تحذيرات.", ephemeral=True)
        return
    
    warns = warnings_db[user_id]
    embed = discord.Embed(title=f"⚠️ تحذيرات {member.display_name}", description=f"إجمالي التحذيرات: {len(warns)}", color=WARN_COLOR)
    
    for idx, warn in enumerate(warns[-5:]):
        moderator = interaction.guild.get_member(int(warn["moderator"]))
        mod_name = moderator.mention if moderator else "غير معروف"
        timestamp = int(datetime.fromisoformat(warn["timestamp"]).timestamp())
        embed.add_field(
            name=f"تحذير #{warn['id']}",
            value=f"**المشرف:** {mod_name}\n**السبب:** {warn['reason']}\n**التاريخ:** <t:{timestamp}:R>",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="حذف_تحذير", description="حذف تحذير معين من عضو")
@app_commands.describe(member="العضو", warn_id="رقم التحذير")
@app_commands.checks.has_permissions(manage_messages=True)
async def removewarn_slash(interaction: discord.Interaction, member: discord.Member, warn_id: int):
    user_id = str(member.id)
    if user_id not in warnings_db or not warnings_db[user_id]:
        await interaction.response.send_message("❌ هذا العضو ليس لديه تحذيرات.", ephemeral=True)
        return
    
    warnings_list = warnings_db[user_id]
    target_warn = next((w for w in warnings_list if w["id"] == warn_id), None)
    
    if not target_warn:
        await interaction.response.send_message(f"❌ لم يتم العثور على تحذير رقم {warn_id}.", ephemeral=True)
        return
    
    warnings_list.remove(target_warn)
    save_data()
    
    embed = discord.Embed(title="✅ تم حذف التحذير", description=f"تم حذف التحذير رقم #{warn_id} من {member.mention}", color=SUCCESS_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="اغلاق", description="قفل القناة الحالية لمنع الأعضاء من الكتابة")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        staff_roles = ["👑 • المالك", "🔮 • المالك المشارك", "⚔️ • الإدارة", "🛡️ • المشرف"]
        for role_name in staff_roles:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                admin_overwrite = interaction.channel.overwrites_for(role)
                admin_overwrite.send_messages = True
                await interaction.channel.set_permissions(role, overwrite=admin_overwrite)
        
        embed = discord.Embed(title="🔒 تم قفل القناة", description="تم قفل هذه القناة. فقط الإداريين يمكنهم الكتابة الآن.", color=ERROR_COLOR)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
        
        public_embed = discord.Embed(title="🔒 تم قفل القناة", description="هذه القناة مغلقة حالياً. سيتم إشعاركم عند فتحها.", color=ERROR_COLOR)
        await interaction.channel.send(embed=public_embed)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ ليس لدي صلاحيات كافية لتعديل صلاحيات القناة.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="فتح", description="فتح القناة المغلقة")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = discord.Embed(title="🔓 تم فتح القناة", description="تم فتح القناة بنجاح. يمكن للجميع الكتابة الآن.", color=SUCCESS_COLOR)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
        
        public_embed = discord.Embed(title="🔓 تم فتح القناة", description="يمكنكم الآن الكتابة في هذه القناة.", color=SUCCESS_COLOR)
        await interaction.channel.send(embed=public_embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="اعداد_السيرفر", description="إعداد السيرفر تلقائياً (سيحذف كل شيء!)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_server_slash(interaction: discord.Interaction):
    confirm_view = View()
    confirm_button = Button(label="نعم، أؤكد الحذف والإعداد", style=discord.ButtonStyle.danger)
    cancel_button = Button(label="إلغاء", style=discord.ButtonStyle.secondary)
    
    async def confirm_callback(interaction_confirm: discord.Interaction):
        if interaction_confirm.user != interaction.user:
            await interaction_confirm.response.send_message("❌ هذا التأكيد ليس لك.", ephemeral=True)
            return
        
        # إرسال رسالة "جاري الإعداد" مرة واحدة فقط
        await interaction_confirm.response.send_message("🔄 جاري إعداد السيرفر... هذا قد يستغرق بعض الوقت.", ephemeral=False)
        
        guild = interaction_confirm.guild
        
        try:
            # === حذف القنوات ===
            for channel in guild.channels:
                try:
                    await channel.delete(reason="إعادة إعداد السيرفر")
                    await asyncio.sleep(0.2)  # تأخير لتجنب Rate Limit
                except Exception as e:
                    print(f"⚠️ فشل حذف القناة {channel.name}: {e}")
            
            # === حذف الرتب ===
            for role in guild.roles:
                # تخطي الرتب التي لا يمكن حذفها
                if role.name == "@everyone" or role.managed or role >= guild.me.top_role:
                    continue
                try:
                    await role.delete(reason="إعادة إعداد السيرفر")
                    await asyncio.sleep(0.2)
                except Exception as e:
                    print(f"⚠️ فشل حذف الرتبة {role.name}: {e}")
            
            # === إنشاء الرتب ===
            for role_info in ROLES:
                try:
                    await guild.create_role(
                        name=role_info["name"],
                        permissions=role_info["permissions"],
                        colour=discord.Colour(role_info["color"]),
                        reason="إعداد السيرفر التلقائي"
                    )
                    await asyncio.sleep(0.2)
                except Exception as e:
                    print(f"⚠️ فشل إنشاء الرتبة {role_info['name']}: {e}")
            
            # === إنشاء القنوات ===
            for category_name, channels in CATEGORIES_AND_CHANNELS.items():
                try:
                    category = await guild.create_category(category_name)
                    
                    if "الدعم الفني" in category_name:
                        ticket_create = await guild.create_text_channel(
                            "🎫・إنشاء-تذكرة",
                            category=category,
                            topic="اضغط على الزر لإنشاء تذكرة"
                        )
                        await ticket_create.send(
                            embed=discord.Embed(title="🎫 نظام التذاكر", description="اضغط على الزر لإنشاء تذكرة", color=INFO_COLOR), 
                            view=TicketView()
                        )
                        await guild.create_text_channel("📋・التذاكر-المفتوحة", category=category)
                    elif "الترحيب" in str(channels):
                        welcome_ch = await guild.create_text_channel(channels[0], category=category)
                        await welcome_ch.send(embed=discord.Embed(title="👋 أهلاً وسهلاً!", description="تم إعداد السيرفر بنجاح!", color=SUCCESS_COLOR))
                    else:
                        for channel_name in channels:
                            if any(x in channel_name for x in ["الروم-العام", "الموسيقى", "الجيمنج"]):
                                await guild.create_voice_channel(channel_name, category=category)
                            else:
                                await guild.create_text_channel(channel_name, category=category)
                    
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    print(f"⚠️ فشل إنشاء الفئة {category_name}: {e}")
            
            # ✅ إرسال رسالة النجاح كـ Followup
            try:
                await interaction_confirm.followup.send(
                    embed=discord.Embed(
                        title="✅ تم إعداد السيرفر بنجاح", 
                        description="تم إنشاء جميع الرتب والقنوات المتاحة.", 
                        color=SUCCESS_COLOR
                    ),
                    ephemeral=False
                )
            except:
                # إذا فشل Followup، أرسل رسالة عامة في أول قناة متاحة
                system_channel = guild.system_channel or next((c for c in guild.text_channels), None)
                if system_channel:
                    await system_channel.send(embed=discord.Embed(
                        title="✅ تم إعداد السيرفر بنجاح", 
                        description="تم إنشاء جميع الرتب والقنوات المتاحة.", 
                        color=SUCCESS_COLOR
                    ))
            
        except Exception as e:
            print(f"❌ خطأ فادح في الإعداد: {e}")
            # محاولة إرسال رسالة الخطأ
            try:
                await interaction_confirm.followup.send(f"❌ حدث خطأ أثناء الإعداد: {e}", ephemeral=True)
            except:
                pass
    
    async def cancel_callback(interaction_cancel: discord.Interaction):
        if interaction_cancel.user != interaction.user:
            await interaction_cancel.response.send_message("❌ هذا الإلغاء ليس لك.", ephemeral=True)
            return
        await interaction_cancel.response.send_message("✅ تم إلغاء عملية الإعداد.", ephemeral=True)
        await interaction.delete_original_response()
    
    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback
    
    confirm_view.add_item(confirm_button)
    confirm_view.add_item(cancel_button)
    
    warning_embed = discord.Embed(
        title="⚠️ تحذير!",
        description="هذا الأمر سيحذف **كل الرتب والقنوات والفئات** في السيرفر!\nهل أنت متأكد من المتابعة؟",
        color=ERROR_COLOR
    )
    await interaction.response.send_message(embed=warning_embed, view=confirm_view, ephemeral=False)

# ==================== الأحداث ====================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 البوت جاهز: {bot.user.name}")
    print(f"📊 متصل بـ {len(bot.guilds)} سيرفر")
    
    load_data()
    bot.add_view(TicketView())
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ تمت مزامنة {len(synced)} أمر Slash")
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {e}")
    print("=" * 50)
    
    bot.loop.create_task(periodic_save())

@bot.event
async def on_member_join(member):
    welcome_channel = discord.utils.get(member.guild.text_channels, name="👋・الترحيب")
    if welcome_channel:
        embed = discord.Embed(
            title=f"🎉 أهلاً بك يا {member.name}!",
            description=f"نورت سيرفر **{member.guild.name}**!\nأنت الآن العضو رقم **{member.guild.member_count}**.",
            color=SUCCESS_COLOR
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"انضم بتاريخ: {member.joined_at.strftime('%Y-%m-%d')}")
        await welcome_channel.send(content=member.mention, embed=embed)
    
    member_role = discord.utils.get(member.guild.roles, name="👤 • العضو")
    if member_role:
        await member.add_roles(member_role)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ ليس لديك الصلاحيات المطلوبة لتنفيذ هذا الأمر.", ephemeral=True)
    elif isinstance(error, app_commands.errors.BotMissingPermissions):
        await interaction.response.send_message("❌ البوت لا يملك الصلاحيات المطلوبة لتنفيذ هذا الأمر.", ephemeral=True)
    elif isinstance(error, app_commands.errors.CommandNotFound):
        await interaction.response.send_message("❌ الأمر غير موجود.", ephemeral=True)
    else:
        print(f"❌ خطأ غير معروف: {error}")
        await interaction.response.send_message("❌ حدث خطأ غير متوقع. تم إبلاغ فريق التطوير.", ephemeral=True)

# حفظ تلقائي كل 5 دقائق
async def periodic_save():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            save_data()
            print(f"💾 تم حفظ البيانات تلقائياً في {datetime.now()}")
        except Exception as e:
            print(f"❌ خطأ في الحفظ التلقائي: {e}")
        await asyncio.sleep(300)

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت ديسكورد المتكامل...")
    print("📌 تأكد من وجود ملف .env مع التوكن")
    
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ فشل تسجيل الدخول: التوكن غير صالح.")
    except Exception as e:
        print(f"❌ حدث خطأ فادح أثناء تشغيل البوت: {e}")

