import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import asyncio
import random
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from typing import Optional

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

# الألوان الفخمة (ثيم متسق)
SUCCESS_COLOR = 0x00FF9F  # أخضر نيون فخم
ERROR_COLOR = 0xFF3860    # أحمر وردي فخم
WARN_COLOR = 0xFFD166     # أصفر ذهبي
INFO_COLOR = 0x118AB2     # أزرق مائي فخم
MAIN_COLOR = 0x9B5DE5     # أرجواني فخم
DARK_BLUE = 0x1E3A8A      # أزرق غامق فخم

# قاعدة البيانات
DATABASE_FILE = "database.json"
tickets_db = {}
tickets_by_channel = {}
warnings_db = {}
levels_db = {}
economy_db = {}
rep_db = {}  # نظام السمعة الجديد

def load_data():
    global warnings_db, levels_db, economy_db, rep_db
    try:
        with open(DATABASE_FILE, 'r') as f:
            data = json.load(f)
            warnings_db = data.get("warnings", {})
            levels_db = data.get("levels", {})
            economy_db = data.get("economy", {})
            rep_db = data.get("reputation", {})
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
            "economy": economy_db,
            "reputation": rep_db
        }
        json.dump(data_to_save, f, indent=4)

# ====================== الرتب والقنوات الفخمة ======================
ROLES = [
    {"name": "👑 • المالك", "color": 0xDC2626, "permissions": discord.Permissions.all()},
    {"name": "🔮 • المالك المشارك", "color": DARK_BLUE, "permissions": discord.Permissions.all()},
    {"name": "⚔️ • الإدارة", "color": 0x7C3AED, "permissions": discord.Permissions(administrator=True)},
    {"name": "🛡️ • المشرف", "color": 0x2563EB, "permissions": discord.Permissions(
        kick_members=True, ban_members=True, manage_messages=True,
        manage_channels=True, mute_members=True, deafen_members=True
    )},
    {"name": "🎯 • المساعد", "color": 0x0891B2, "permissions": discord.Permissions(
        kick_members=True, manage_messages=True, mute_members=True
    )},
    {"name": "💎 • البوستر", "color": 0xEC4899, "permissions": discord.Permissions.none()},
    {"name": "🏆 • الرائع", "color": 0xF59E0B, "permissions": discord.Permissions.none()},
    {"name": "👤 • العضو", "color": 0x6B7280, "permissions": discord.Permissions.none()},
]

ROLE_HIERARCHY = [role["name"] for role in ROLES]

CATEGORIES_AND_CHANNELS = {
    "📢 • الإعلانات": ["📣・الإعلانات-الرسمية", "📰・الأخبار", "🎉・الفعاليات", "🎁・الجوائز-اليومية"],
    "💬 • الدردشة": ["💭・الدردشة-العامة", "🎮・الألعاب", "🎨・الفن-والإبداع", "📷・الصور-والميمز", "🤖・أوامر-البوت"],
    "🎵 • الصوتيات": ["🔊・الروم-العام", "🎵・الموسيقى", "🎮・الجيمنج-1", "🎮・الجيمنج-2", "🎤・البودكاست"],
    "🎫 • الدعم الفني": ["🎫・إنشاء-تذكرة", "📋・التذاكر-المفتوحة"],
    "⚙️ • الإدارة": ["🛠️・إدارة-السيرفر", "📊・السجلات", "⚠️・البلاغات", "🚨・التحذيرات"],
    "ℹ️ • المعلومات": ["📜・القوانين", "👋・الترحيب", "📌・الروابط-المهمة", "📊・الإحصائيات", "📈・التوب"]
}

# ====================== نظام التذاكر المتطور ======================
class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="دعم فني", description="مشاكل تقنية وأسئلة حول البوت", emoji="💻", value="tech_support"),
            discord.SelectOption(label="مشكلة بالسيرفر", description="مشاكل متعلقة بإعدادات السيرفر", emoji="⚙️", value="server_problem"),
            discord.SelectOption(label="شكوى على عضو/إداري", description="للشكاوى ضد الأعضاء أو فريق العمل", emoji="⚖️", value="complaint"),
            discord.SelectOption(label="اقتراح", description="اقتراحات لتحسين السيرفر", emoji="💡", value="suggestion"),
            discord.SelectOption(label="طلب ترقية", description="طلب ترقية لرتبة معينة", emoji="📈", value="promotion"),
            discord.SelectOption(label="أخرى", description="أي موضوع آخر", emoji="📦", value="other")
        ]
        super().__init__(placeholder="🎫 اختر نوع التذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_type_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        ticket_type = self.values[0]

        # التحقق من وجود تذكرة مفتوحة
        if str(member.id) in tickets_db and any(ch.id == tickets_db[str(member.id)]["channel_id"] for ch in guild.channels):
            embed = discord.Embed(title="❌ تذكرة مفتوحة بالفعل", description="لديك تذكرة مفتوحة بالفعل، يرجى إغلاقها أولاً.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="🎫 • الدعم الفني")
        if not category:
            embed = discord.Embed(title="❌ خطأ", description="لا يمكن العثور على قسم الدعم الفني.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # إعداد الصلاحيات
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }

        admin_role = discord.utils.get(guild.roles, name="⚔️ • الإدارة")
        mod_role = discord.utils.get(guild.roles, name="🛡️ • المشرف")
        coowner_role = discord.utils.get(guild.roles, name="🔮 • المالك المشارك")

        if admin_role: overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        if mod_role: overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        if coowner_role: overwrites[coowner_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

        # إنشاء القناة
        ticket_channel = await guild.create_text_channel(
            f"🎫┃{member.name}", 
            category=category, 
            overwrites=overwrites,
            topic=f"تذكرة: {member.name} | النوع: {ticket_type}"
        )

        # حفظ البيانات
        ticket_data = {
            "channel_id": ticket_channel.id, 
            "type": ticket_type, 
            "accepted_by": None, 
            "owner_id": str(member.id),
            "created_at": datetime.now().isoformat(),
            "status": "مفتوحة"
        }
        tickets_db[str(member.id)] = ticket_data
        tickets_by_channel[ticket_channel.id] = ticket_data

        # تعيين أسماء الأنواع
        type_names = {
            "tech_support": "💻 دعم فني", 
            "server_problem": "⚙️ مشكلة بالسيرفر", 
            "complaint": "⚖️ شكوى",
            "suggestion": "💡 اقتراح",
            "promotion": "📈 طلب ترقية",
            "other": "📦 أخرى"
        }

        # إرسال رسالة التذكرة
        terms_embed = discord.Embed(
            title="📜 قواعد وشروط التذاكر", 
            description="• يُمنع المنشن غير الضروري.\n• شرح المشكلة بوضوح واختصار.\n• احترام فريق الدعم.\n• الرد خلال 24 ساعة.", 
            color=WARN_COLOR
        )
        
        embed = discord.Embed(
            title=f"🎫 تذكرة جديدة: {type_names[ticket_type]}", 
            description=f"مرحباً {member.mention}،\n\nالرجاء الانتظار، سيقوم أحد أعضاء فريق الدعم بالرد عليك قريباً.", 
            color=SUCCESS_COLOR
        )
        embed.add_field(name="👤 صاحب التذكرة", value=member.mention, inline=True)
        embed.add_field(name="🕐 تم الإنشاء", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        embed.set_thumbnail(url=member.display_avatar.url)

        mention_text = ""
        if ticket_type == "complaint" and coowner_role:
            mention_text = f"{coowner_role.mention}"
        elif admin_role:
            mention_text = f"{admin_role.mention}"

        await ticket_channel.send(content=mention_text, embeds=[terms_embed, embed], view=TicketManagementView(ticket_channel.id))
        
        success_embed = discord.Embed(
            title="✅ تم إنشاء التذكرة", 
            description=f"تم إنشاء تذكرتك في {ticket_channel.mention}", 
            color=SUCCESS_COLOR
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

class RenameModal(Modal, title="إعادة تسمية التذكرة"):
    new_name = TextInput(label="الاسم الجديد", placeholder="أدخل اسم القناة الجديد...", required=True, max_length=100)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.channel.edit(name=self.new_name.value)
            embed = discord.Embed(title="✅ تم التعديل", description=f"تم تغيير اسم القناة إلى: **{self.new_name.value}**", color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AddUserModal(Modal, title="إضافة عضو للتذكرة"):
    user_id = TextInput(label="معرف العضو (ID)", placeholder="أدخل ID العضو...", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value))
            if not user:
                raise ValueError("المستخدم غير موجود")
            
            overwrites = interaction.channel.overwrites_for(user)
            overwrites.update(read_messages=True, send_messages=True)
            await interaction.channel.set_permissions(user, overwrite=overwrites)
            
            embed = discord.Embed(title="✅ تمت الإضافة", description=f"تم إضافة {user.mention} للتذكرة", color=SUCCESS_COLOR)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class TicketManagementView(View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="✋ قبول التذكرة", style=discord.ButtonStyle.green, custom_id="accept_ticket", emoji="✋")
    async def accept_ticket(self, interaction: discord.Interaction, button: Button):
        ticket_data = tickets_by_channel.get(self.channel_id)
        if not ticket_data:
            return
        
        if ticket_data["accepted_by"]:
            embed = discord.Embed(title="❌ تم قبولها مسبقاً", description=f"التذكرة مقبولة بالفعل من قبل <@{ticket_data['accepted_by']}>", color=WARN_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        ticket_data["accepted_by"] = str(interaction.user.id)
        ticket_data["status"] = "قيد المعالجة"
        tickets_by_channel[self.channel_id] = ticket_data
        
        # تحديث قاعدة البيانات
        owner_id = ticket_data["owner_id"]
        if owner_id in tickets_db:
            tickets_db[owner_id] = ticket_data
        
        embed = discord.Embed(title="✅ تم قبول التذكرة", description=f"التذكرة الآن تحت إشراف {interaction.user.mention}", color=SUCCESS_COLOR)
        await interaction.response.send_message(embed=embed)
        
        # إضافة زر جديد للإغلاق
        self.add_item(Button(label="🔒 إغلاق", style=discord.ButtonStyle.red, custom_id="close_ticket_btn", emoji="🔒"))
        await interaction.message.edit(view=self)

    @discord.ui.button(label="📝 إعادة تسمية", style=discord.ButtonStyle.blurple, custom_id="rename_ticket", emoji="📝")
    async def rename_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(label="➕ إضافة عضو", style=discord.ButtonStyle.gray, custom_id="add_user", emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(label="📄 نسخة", style=discord.ButtonStyle.gray, custom_id="transcript", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        messages = []
        async for msg in interaction.channel.history(limit=1000, oldest_first=True):
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.name}: {msg.content}")
        
        transcript = "\n".join(messages)
        
        # إنشاء ملف نصي
        filename = f"transcript-{interaction.channel.name}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(transcript)
        
        embed = discord.Embed(title="📄 تم إنشاء النسخة", description="تم إنشاء نسخة من التذكرة", color=SUCCESS_COLOR)
        await interaction.followup.send(embed=embed, file=discord.File(filename), ephemeral=True)
        
        os.remove(filename)

    @discord.ui.button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        # تأكيد الإغلاق
        confirm_view = View()
        confirm_button = Button(label="نعم، أغلقها", style=discord.ButtonStyle.danger, emoji="✅")
        cancel_button = Button(label="إلغاء", style=discord.ButtonStyle.secondary, emoji="❌")
        
        async def confirm_close(interaction_confirm):
            if interaction_confirm.user != interaction.user:
                await interaction_confirm.response.send_message("❌ هذا ليس لك", ephemeral=True)
                return
            
            await interaction_confirm.response.send_message("⏳ جاري إغلاق التذكرة خلال 5 ثواني...", ephemeral=False)
            
            # حذف التذكرة من قاعدة البيانات
            owner_id = tickets_by_channel.get(self.channel_id, {}).get("owner_id")
            if owner_id and owner_id in tickets_db:
                del tickets_db[owner_id]
            if self.channel_id in tickets_by_channel:
                del tickets_by_channel[self.channel_id]
            
            await asyncio.sleep(5)
            try:
                await interaction_confirm.channel.delete(reason=f"أغلق بواسطة {interaction.user}")
            except discord.NotFound:
                pass
        
        async def cancel_close(interaction_cancel):
            if interaction_cancel.user != interaction.user:
                await interaction_cancel.response.send_message("❌ هذا ليس لك", ephemeral=True)
                return
            await interaction_cancel.response.send_message("✅ تم إلغاء الإغلاق", ephemeral=True)
        
        confirm_button.callback = confirm_close
        cancel_button.callback = cancel_close
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        embed = discord.Embed(title="⚠️ تأكيد الإغلاق", description="هل أنت متأكد من إغلاق هذه التذكرة؟", color=WARN_COLOR)
        await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="🗑️ حذف فوري", style=discord.ButtonStyle.red, custom_id="delete_ticket", emoji="🗑️")
    async def delete_ticket(self, interaction: discord.Interaction, button: Button):
        high_staff = ["👑 • المالك", "🔮 • المالك المشارك", "⚔️ • الإدارة"]
        user_roles = [role.name for role in interaction.user.roles]
        
        if not any(role in high_staff for role in user_roles):
            embed = discord.Embed(title="❌ صلاحية مرفوضة", description="هذه الصلاحية للإدارة العليا فقط.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(title="🗑️ حذف فوري", description="سيتم حذف القناة فوراً...", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
        # حذف التذكرة من قاعدة البيانات
        owner_id = tickets_by_channel.get(self.channel_id, {}).get("owner_id")
        if owner_id and owner_id in tickets_db:
            del tickets_db[owner_id]
        if self.channel_id in tickets_by_channel:
            del tickets_by_channel[self.channel_id]

        try:
            await interaction.channel.delete(reason=f"حذف فوري بواسطة {interaction.user}")
        except discord.NotFound:
            pass

# ==================== نظام المستويات والاقتصاد المتطور ====================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    user_id = str(message.author.id)
    guild_id = str(message.guild.id)
    
    # نظام المستويات
    if user_id not in levels_db:
        levels_db[user_id] = {"xp": 0, "level": 1, "messages": 0, "last_xp": datetime.now().isoformat()}
    
    # منع الـ XP المستمر
    last_xp_time = datetime.fromisoformat(levels_db[user_id]["last_xp"])
    if datetime.now() - last_xp_time < timedelta(seconds=60):
        await bot.process_commands(message)
        return
    
    levels_db[user_id]["messages"] += 1
    levels_db[user_id]["xp"] += random.randint(10, 25)
    levels_db[user_id]["last_xp"] = datetime.now().isoformat()
    
    xp = levels_db[user_id]["xp"]
    level = levels_db[user_id]["level"]
    xp_needed = level * 150 + (level * 50)
    
    if xp >= xp_needed:
        levels_db[user_id]["level"] += 1
        levels_db[user_id]["xp"] = 0
        new_level = levels_db[user_id]["level"]
        
        # مكافأة الترقية
        if user_id not in economy_db:
            economy_db[user_id] = {"coins": 0, "bank": 0, "last_daily": None}
        economy_db[user_id]["coins"] += new_level * 100
        
        embed = discord.Embed(
            title="🎉 ترقية مستوى!", 
            description=f"مبروك {message.author.mention}، لقد وصلت للمستوى **{new_level}**!\n🎁 حصلت على **{new_level * 100}** 🪙", 
            color=0xFFD700
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        await message.channel.send(embed=embed, delete_after=15)
    
    # نظام الاقتصاد
    if user_id not in economy_db:
        economy_db[user_id] = {"coins": 0, "bank": 0, "last_daily": None}
    
    economy_db[user_id]["coins"] += random.randint(2, 5)
    
    # نظام السمعة
    if user_id not in rep_db:
        rep_db[user_id] = {"rep": 0, "last_rep": None}
    
    # حفظ تلقائي عشوائي
    if random.randint(1, 50) == 1:
        save_data()

    await bot.process_commands(message)

# ==================== Slash Commands ====================
@bot.tree.command(name="ping", description="عرض سرعة استجابة البوت")
async def ping_slash(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 بينج!", description=f"سرعة الاستجابة: **{latency}ms**", color=INFO_COLOR)
    embed.set_footer(text=f"طلب بواسطة {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="عرض معلومات السيرفر")
async def serverinfo_slash(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"ℹ️ معلومات {guild.name}", color=INFO_COLOR)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 المالك", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 الأعضاء", value=guild.member_count, inline=True)
    embed.add_field(name="📊 التصنيف", value=str(guild.verification_level), inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
    embed.add_field(name="🎭 الرتب", value=len(guild.roles), inline=True)
    embed.add_field(name="💬 القنوات", value=len(guild.channels), inline=True)
    embed.add_field(name="🌟 البوسترز", value=guild.premium_subscription_count, inline=True)
    embed.set_footer(text=f"ID: {guild.id}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="عرض معلومات المستخدم")
@app_commands.describe(member="العضو")
async def userinfo_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    roles = [role.mention for role in member.roles[1:]]  # تخطي @everyone
    
    embed = discord.Embed(title=f"ℹ️ معلومات {member.display_name}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 الاسم", value=member.name, inline=True)
    embed.add_field(name="🏷️ التاغ", value=member.discriminator, inline=True)
    embed.add_field(name="🆔 الID", value=member.id, inline=True)
    embed.add_field(name="📅 انضم للسيرفر", value=f"<t:{int(member.joined_at.timestamp())}:D>", inline=True)
    embed.add_field(name="📅 إنشاء الحساب", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
    
    if roles:
        embed.add_field(name=f"🎭 الرتب ({len(roles)})", value=" ".join(roles[:5]) + ("..." if len(roles) > 5 else ""), inline=False)
    
    embed.add_field(name="🎨 اللون", value=str(member.color), inline=True)
    embed.set_footer(text=f"طلب بواسطة {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="عرض صورة العضو")
@app_commands.describe(member="العضو")
async def avatar_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ صورة {member.display_name}", color=member.color)
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"طلب بواسطة {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="مستوى", description="عرض مستوى العضو وخبرته")
@app_commands.describe(member="العضو الذي تريد عرض مستواه")
async def level_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    user_id = str(member.id)
    
    data = levels_db.get(user_id, {"xp": 0, "level": 1, "messages": 0})
    xp_needed = data["level"] * 150 + (data["level"] * 50)
    
    progress = int((data['xp'] / xp_needed) * 20) if xp_needed > 0 else 0
    progress_bar = '🟩' * progress + '⬛' * (20 - progress)

    embed = discord.Embed(title=f"📊 مستوى {member.display_name}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏆 المستوى", value=f"**{data['level']}**", inline=True)
    embed.add_field(name="💬 الرسائل", value=f"**{data['messages']:,}**", inline=True)
    embed.add_field(name="⭐ الخبرة", value=f"**{data['xp']} / {xp_needed}**", inline=True)
    embed.add_field(name="📈 التقدم", value=f"`{progress_bar}` **{int((data['xp']/xp_needed)*100)}%**", inline=False)
    embed.set_footer(text=f"ID: {member.id}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ترتيب", description="عرض قائمة المتصدرين في المستويات")
async def leaderboard_slash(interaction: discord.Interaction):
    sorted_users = sorted(levels_db.items(), key=lambda item: (item[1]['level'], item[1]['xp']), reverse=True)[:10]
    
    embed = discord.Embed(title="🏆 لوحة المتصدرين", description="أعلى 10 أعضاء في السيرفر", color=0xFFD700)
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, (user_id, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(user_id))
        if member:
            embed.add_field(
                name=f"{medals[idx-1]} {member.display_name}", 
                value=f"**المستوى:** {data['level']} | **الخبرة:** {data['xp']} | **الرسائل:** {data['messages']:,}", 
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

# ==================== الأوامر الاقتصادية المتقدمة ====================
@bot.tree.command(name="يومي", description="الحصول على المكافأة اليومية")
async def daily_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    user_data = economy_db.get(user_id, {"coins": 0, "bank": 0, "last_daily": None})
    last_daily_str = user_data.get("last_daily")
    
    if last_daily_str:
        last_daily = datetime.fromisoformat(last_daily_str)
        time_left = timedelta(hours=23, minutes=30) - (datetime.now() - last_daily)
        if time_left.total_seconds() > 0:
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            embed = discord.Embed(
                title="⏰ مكافأتك معلقة", 
                description=f"لقد حصلت على مكافأتك بالفعل!\nتنتظر: **{hours}س {minutes}د**", 
                color=WARN_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
    reward = random.randint(300, 1000)
    bonus = random.randint(0, 500)
    total_reward = reward + bonus
    
    user_data["coins"] = user_data.get("coins", 0) + total_reward
    user_data["last_daily"] = datetime.now().isoformat()
    economy_db[user_id] = user_data
    save_data()
    
    embed = discord.Embed(title="🎁 مكافأة يومية!", color=SUCCESS_COLOR)
    embed.description = f"لقد حصلت على **{reward}** 🪙!"
    if bonus > 0:
        embed.description += f"\n✨ مكافأة إضافية: **+{bonus}** 🪙"
    embed.set_footer(text=f"إجمالي: {total_reward} 🪙")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="رصيد", description="عرض رصيدك")
@app_commands.describe(member="العضو")
async def balance_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    user_id = str(member.id)
    data = economy_db.get(user_id, {"coins": 0, "bank": 0, "last_daily": None})
    
    embed = discord.Embed(title=f"💰 رصيد {member.display_name}", color=SUCCESS_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🪙 النقود", value=f"**{data['coins']:,}**", inline=True)
    embed.add_field(name="🏦 البنك", value=f"**{data['bank']:,}**", inline=True)
    embed.add_field(name="📊 الإجمالي", value=f"**{data['coins'] + data['bank']:,}** 🪙", inline=False)
    embed.set_footer(text=f"طلب بواسطة {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ايداع", description="إيداع النقود في البنك")
@app_commands.describe(amount="المبلغ (أو all للكل)")
async def deposit_slash(interaction: discord.Interaction, amount: str):
    user_id = str(interaction.user.id)
    data = economy_db.get(user_id, {"coins": 0, "bank": 0})
    
    if amount.lower() == "all":
        amount = data["coins"]
    else:
        try:
            amount = int(amount)
        except:
            embed = discord.Embed(title="❌ خطأ", description="يرجى إدخال رقم صحيح أو 'all'", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    if amount <= 0:
        embed = discord.Embed(title="❌ خطأ", description="المبلغ يجب أن يكون أكبر من 0", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if data["coins"] < amount:
        embed = discord.Embed(title="❌ خطأ", description="ليس لديك نقود كافية!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data["coins"] -= amount
    data["bank"] += amount
    economy_db[user_id] = data
    save_data()
    
    embed = discord.Embed(title="✅ تم الإيداع", description=f"تم إيداع **{amount}** 🪙 في البنك", color=SUCCESS_COLOR)
    embed.add_field(name="الرصيد الجديد", value=f"🪙 {data['coins']} | 🏦 {data['bank']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="سحب", description="سحب النقود من البنك")
@app_commands.describe(amount="المبلغ")
async def withdraw_slash(interaction: discord.Interaction, amount: str):
    user_id = str(interaction.user.id)
    data = economy_db.get(user_id, {"coins": 0, "bank": 0})
    
    if amount.lower() == "all":
        amount = data["bank"]
    else:
        try:
            amount = int(amount)
        except:
            embed = discord.Embed(title="❌ خطأ", description="يرجى إدخال رقم صحيح أو 'all'", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    if amount <= 0:
        embed = discord.Embed(title="❌ خطأ", description="المبلغ يجب أن يكون أكبر من 0", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if data["bank"] < amount:
        embed = discord.Embed(title="❌ خطأ", description="ليس لديك رصيد كافٍ في البنك!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data["bank"] -= amount
    data["coins"] += amount
    economy_db[user_id] = data
    save_data()
    
    embed = discord.Embed(title="✅ تم السحب", description=f"تم سحب **{amount}** 🪙 من البنك", color=SUCCESS_COLOR)
    embed.add_field(name="الرصيد الجديد", value=f"🪙 {data['coins']} | 🏦 {data['bank']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="تحويل", description="تحويل النقود لعضو آخر")
@app_commands.describe(member="العضو", amount="المبلغ")
async def transfer_slash(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.bot:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن التحويل للبوتات!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if amount <= 0:
        embed = discord.Embed(title="❌ خطأ", description="المبلغ يجب أن يكون أكبر من 0", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    sender_id = str(interaction.user.id)
    receiver_id = str(member.id)
    
    sender_data = economy_db.get(sender_id, {"coins": 0, "bank": 0})
    receiver_data = economy_db.get(receiver_id, {"coins": 0, "bank": 0})
    
    if sender_data["coins"] < amount:
        embed = discord.Embed(title="❌ خطأ", description="ليس لديك نقود كافية!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # خصم 5% ضريبة
    tax = int(amount * 0.05)
    final_amount = amount - tax
    
    sender_data["coins"] -= amount
    receiver_data["coins"] += final_amount
    
    economy_db[sender_id] = sender_data
    economy_db[receiver_id] = receiver_data
    save_data()
    
    embed = discord.Embed(title="✅ تم التحويل", color=SUCCESS_COLOR)
    embed.description = f"تم تحويل **{final_amount}** 🪙 إلى {member.mention}"
    embed.add_field(name="💸 الضريبة (5%)", value=f"-{tax} 🪙", inline=True)
    embed.set_footer(text=f"الرصيد الجديد: {sender_data['coins']} 🪙")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="سمعة", description="إعطاء نقطة سمعة لعضو")
@app_commands.describe(member="العضو")
async def rep_slash(interaction: discord.Interaction, member: discord.Member):
    if member.bot:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن إعطاء سمعة للبوتات!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.id == interaction.user.id:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكنك إعطاء سمعة لنفسك!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    
    if user_id not in rep_db:
        rep_db[user_id] = {"rep": 0, "last_rep": None}
    
    last_rep = rep_db[user_id]["last_rep"]
    if last_rep:
        last_rep_time = datetime.fromisoformat(last_rep)
        if datetime.now() - last_rep_time < timedelta(hours=12):
            time_left = timedelta(hours=12) - (datetime.now() - last_rep_time)
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            embed = discord.Embed(title="⏰ انتظر", description=f"يمكنك إعطاء سمعة كل 12 ساعة!\nتنتظر: **{hours}س {minutes}د**", color=WARN_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    rep_db[user_id]["last_rep"] = datetime.now().isoformat()
    
    receiver_id = str(member.id)
    if receiver_id not in rep_db:
        rep_db[receiver_id] = {"rep": 0, "last_rep": None}
    
    rep_db[receiver_id]["rep"] += 1
    save_data()
    
    embed = discord.Embed(title="✅ تم إعطاء سمعة", description=f"لقد أعطيت نقطة سمعة لـ {member.mention}!\n🏆 سمعته الآن: **{rep_db[receiver_id]['rep']}**", color=SUCCESS_COLOR)
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
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن إعطاء رتب للبوتات.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
        
    user_highest_role_name, user_rank = get_highest_staff_role(interaction.user.roles)
    target_role_rank = get_role_rank(role.name)

    if user_rank == 999 and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="❌ خطأ", description="ليس لديك صلاحية إعطاء رتب إدارية!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator and target_role_rank <= user_rank:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكنك إعطاء رتبة أعلى من رتبتك أو مساوية لها.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if role.name not in ROLE_HIERARCHY:
        await member.add_roles(role)
        embed = discord.Embed(title="⚠️ خارج النظام", description="تم إضافة الرتبة خارج النظام الهرمي.", color=WARN_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    roles_to_remove = [r for r in member.roles if r.name in ROLE_HIERARCHY]
    removed_roles_names = [r.mention for r in roles_to_remove]

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"تغيير الرتبة بواسطة {interaction.user}")
        
        await member.add_roles(role, reason=f"إعطاء رتبة بواسطة {interaction.user}")

        embed = discord.Embed(title="✅ تم تحديث الرتبة", color=SUCCESS_COLOR)
        embed.description = f"تم تحديث رتبة {member.mention}."
        embed.add_field(name="➕ الجديدة", value=role.mention, inline=True)
        if removed_roles_names:
            embed.add_field(name="➖ المحذوفة", value=" ".join(removed_roles_names[:3]) + ("..." if len(removed_roles_names) > 3 else ""), inline=True)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        embed = discord.Embed(title="❌ خطأ", description="ليس لدي الصلاحيات الكافية. قد تكون رتبة البوت أقل!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="طرد", description="طرد عضو من السيرفر")
@app_commands.describe(member="العضو", reason="سبب الطرد")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member.bot:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن طرد البوتات.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكنك طرد شخص برتبة أعلى منك.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.top_role >= interaction.guild.me.top_role:
        embed = discord.Embed(title="❌ خطأ", description="رتبة البوت أقل من رتبة العضو!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        await member.kick(reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}")
        
        embed = discord.Embed(title="✅ تم الطرد", description=f"تم طرد {member.mention} بنجاح", color=ERROR_COLOR)
        if reason:
            embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title="🚫 تم طردك", description=f"لقد تم طردك من سيرفر **{interaction.guild.name}**", color=ERROR_COLOR)
            if reason:
                dm_embed.add_field(name="السبب", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"فشل الطرد: {e}", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="حظر", description="حظر عضو من السيرفر")
@app_commands.describe(member="العضو", reason="سبب الحظر", delete_days="عدد أيام حذف الرسائل (0-7)")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None, delete_days: int = 0):
    if delete_days < 0 or delete_days > 7:
        embed = discord.Embed(title="❌ خطأ", description="عدد الأيام يجب أن يكون بين 0 و 7.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.bot:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن حظر البوتات.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكنك حظر شخص برتبة أعلى منك.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.top_role >= interaction.guild.me.top_role:
        embed = discord.Embed(title="❌ خطأ", description="رتبة البوت أقل من رتبة العضو!", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        await member.ban(reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}", delete_message_seconds=delete_days*86400)
        
        embed = discord.Embed(title="✅ تم الحظر", description=f"تم حظر {member.mention} بنجاح", color=ERROR_COLOR)
        embed.add_field(name="🗑️ حذف الرسائل", value=f"آخر {delete_days} أيام", inline=True)
        if reason:
            embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title="⛔ تم حظرك", description=f"لقد تم حظرك من سيرفر **{interaction.guild.name}**", color=ERROR_COLOR)
            if reason:
                dm_embed.add_field(name="السبب", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"فشل الحظر: {e}", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="فك_حظر", description="فك حظر عضو")
@app_commands.describe(user_id="معرف العضو (ID)", reason="سبب فك الحظر")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = None):
    try:
        user_id_int = int(user_id)
    except:
        embed = discord.Embed(title="❌ خطأ", description="معرف المستخدم غير صالح.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        banned_users = [ban async for ban in interaction.guild.bans()]
        target_ban = next((ban for ban in banned_users if ban.user.id == user_id_int), None)
        
        if not target_ban:
            embed = discord.Embed(title="❌ خطأ", description="هذا المستخدم غير محظور.", color=ERROR_COLOR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.guild.unban(target_ban.user, reason=f"بواسطة {interaction.user}: {reason or 'بدون سبب'}")
        
        embed = discord.Embed(title="✅ تم فك الحظر", description=f"تم فك حظر {target_ban.user.mention}", color=SUCCESS_COLOR)
        if reason:
            embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"فشل فك الحظر: {e}", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="مسح", description="مسح عدد معين من الرسائل")
@app_commands.describe(amount="عدد الرسائل (1-100)", member="مسح رسائل عضو معين فقط")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_slash(interaction: discord.Interaction, amount: int, member: discord.Member = None):
    if amount < 1 or amount > 100:
        embed = discord.Embed(title="❌ خطأ", description="يجب أن يكون العدد بين 1 و 100.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        if member:
            def check(msg):
                return msg.author.id == member.id
            deleted = await interaction.channel.purge(limit=amount, check=check)
        else:
            deleted = await interaction.channel.purge(limit=amount)
        
        embed = discord.Embed(title="✅ تم المسح", description=f"تم مسح **{len(deleted)}** رسالة", color=SUCCESS_COLOR)
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
        embed = discord.Embed(title="❌ خطأ", description="يجب أن يكون العدد بين 0 و 21600 (6 ساعات).", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        await interaction.channel.edit(slowmode_delay=seconds)
        
        if seconds == 0:
            embed = discord.Embed(title="✅ تم تعطيل وضع الكتابة البطيء", description="يمكن للجميع الكتابة الآن بدون تأخير", color=SUCCESS_COLOR)
        else:
            embed = discord.Embed(title="✅ تم تفعيل وضع الكتابة البطيء", description=f"يجب الانتظار **{seconds}** ثانية بين كل رسالة", color=SUCCESS_COLOR)
        
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"فشل التحديث: {e}", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="تحذير", description="إعطاء تحذير لعضو")
@app_commands.describe(member="العضو", reason="سبب التحذير")
@app_commands.checks.has_permissions(kick_members=True)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member.bot:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكن إعطاء تحذير للبوتات.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="❌ خطأ", description="لا يمكنك تحذير شخص برتبة أعلى منك.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
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
        dm_embed.add_field(name="👤 المشرف", value=interaction.user.mention, inline=False)
        if reason:
            dm_embed.add_field(name="📝 السبب", value=reason, inline=False)
        await member.send(embed=dm_embed)
    except:
        pass
    
    total_warns = len(warnings_db[user_id])
    max_warns = 3
    
    embed = discord.Embed(title="⚠️ تم إعطاء تحذير", color=WARN_COLOR)
    embed.description = f"تم إعطاء تحذير لـ {member.mention}"
    embed.add_field(name="📊 عدد التحذيرات", value=f"**{total_warns}/{max_warns}**", inline=True)
    if reason:
        embed.add_field(name="📝 السبب", value=reason, inline=False)
    
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
        embed = discord.Embed(title="✅ لا توجد تحذيرات", description=f"{member.mention} ليس لديه أي تحذيرات.", color=SUCCESS_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    warns = warnings_db[user_id]
    embed = discord.Embed(title=f"⚠️ تحذيرات {member.display_name}", description=f"إجمالي التحذيرات: **{len(warns)}/3**", color=WARN_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    for idx, warn in enumerate(warns[-5:]):
        moderator = interaction.guild.get_member(int(warn["moderator"]))
        mod_name = moderator.mention if moderator else "غير معروف"
        timestamp = int(datetime.fromisoformat(warn["timestamp"]).timestamp())
        embed.add_field(
            name=f"🚨 تحذير #{warn['id']}",
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
        embed = discord.Embed(title="❌ خطأ", description="هذا العضو ليس لديه تحذيرات.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    warnings_list = warnings_db[user_id]
    target_warn = next((w for w in warnings_list if w["id"] == warn_id), None)
    
    if not target_warn:
        embed = discord.Embed(title="❌ خطأ", description=f"لم يتم العثور على تحذير رقم {warn_id}.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    warnings_list.remove(target_warn)
    save_data()
    
    embed = discord.Embed(title="✅ تم حذف التحذير", description=f"تم حذف التحذير رقم #{warn_id} من {member.mention}", color=SUCCESS_COLOR)
    embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
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
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed)
        
        public_embed = discord.Embed(title="🔒 تم قفل القناة", description="هذه القناة مغلقة حالياً. سيتم إشعاركم عند فتحها.", color=ERROR_COLOR)
        await interaction.channel.send(embed=public_embed)
        
    except discord.Forbidden:
        embed = discord.Embed(title="❌ خطأ", description="ليس لدي صلاحيات كافية.", color=ERROR_COLOR)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="فتح", description="فتح القناة المغلقة")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = discord.Embed(title="🔓 تم فتح القناة", description="يمكن للجميع الكتابة الآن.", color=SUCCESS_COLOR)
        embed.set_footer(text=f"بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed)
        
        public_embed = discord.Embed(title="🔓 تم فتح القناة", description="يمكنكم الآن الكتابة في هذه القناة.", color=SUCCESS_COLOR)
        await interaction.channel.send(embed=public_embed)
        
    except Exception as e:
        embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="اعداد_السيرفر", description="إعداد السيرفر تلقائياً (سيحذف كل شيء!)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_server_slash(interaction: discord.Interaction):
    confirm_view = View()
    confirm_button = Button(label="نعم، أؤكد الحذف والإعداد", style=discord.ButtonStyle.danger, emoji="⚠️")
    cancel_button = Button(label="إلغاء", style=discord.ButtonStyle.secondary, emoji="✅")
    
    async def confirm_callback(interaction_confirm: discord.Interaction):
        if interaction_confirm.user != interaction.user:
            await interaction_confirm.response.send_message("❌ هذا التأكيد ليس لك.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🔄 جاري الإعداد...", description="يرجى الانتظار قليلاً...", color=INFO_COLOR)
        await interaction_confirm.response.edit_message(embed=embed, view=None)
        
        guild = interaction_confirm.guild
        
        try:
            # === حذف القنوات ===
            for channel in guild.channels:
                try:
                    await channel.delete(reason="إعادة إعداد السيرفر")
                    await asyncio.sleep(0.2)
                except:
                    pass
            
            # === حذف الرتب ===
            for role in guild.roles:
                if role.name == "@everyone" or role.managed or role >= guild.me.top_role:
                    continue
                try:
                    await role.delete(reason="إعادة إعداد السيرفر")
                    await asyncio.sleep(0.2)
                except:
                    pass
            
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
                except:
                    pass
            
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
                        embed = discord.Embed(
                            title="👋 أهلاً وسهلاً!", 
                            description="تم إعداد السيرفر بنجاح!\nاضغط على الزر أدناه لإنشاء أول تذكرة.", 
                            color=SUCCESS_COLOR
                        )
                        await welcome_ch.send(embed=embed, view=TicketView())
                    else:
                        for channel_name in channels:
                            if any(x in channel_name for x in ["الروم-العام", "الموسيقى", "الجيمنج"]):
                                await guild.create_voice_channel(channel_name, category=category)
                            else:
                                await guild.create_text_channel(channel_name, category=category)
                    
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    print(f"خطأ: {e}")
            
            # رسالة النجاح
            success_embed = discord.Embed(
                title="✅ اكتمل الإعداد", 
                description="تم إنشاء جميع الرتب والقنوات بنجاح!", 
                color=SUCCESS_COLOR
            )
            await interaction_confirm.edit_original_response(embed=success_embed)
            
        except Exception as e:
            error_embed = discord.Embed(title="❌ خطأ", description=f"حدث خطأ: {e}", color=ERROR_COLOR)
            await interaction_confirm.edit_original_response(embed=error_embed)
    
    async def cancel_callback(interaction_cancel: discord.Interaction):
        if interaction_cancel.user != interaction.user:
            await interaction_cancel.response.send_message("❌ هذا الإلغاء ليس لك.", ephemeral=True)
            return
        
        cancel_embed = discord.Embed(title="✅ تم الإلغاء", description="تم إلغاء عملية الإعداد.", color=SUCCESS_COLOR)
        await interaction_cancel.response.edit_message(embed=cancel_embed, view=None)
    
    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback
    
    confirm_view.add_item(confirm_button)
    confirm_view.add_item(cancel_button)
    
    warning_embed = discord.Embed(
        title="⚠️ تحذير خطير!",
        description="هذا الأمر سيحذف **كل الرتب والقنوات والفئات** في السيرفر!\n\n**لا يمكن التراجع عن هذا الإجراء!**\n\nهل أنت متأكد من المتابعة؟",
        color=ERROR_COLOR
    )
    warning_embed.set_footer(text="تأكيد مطلوب من Administrator")
    await interaction.response.send_message(embed=warning_embed, view=confirm_view, ephemeral=False)

# ==================== الأحداث ====================
@bot.event
async def on_ready():
    print("=" * 60)
    print(f"🤖 البوت جاهز: {bot.user.name}")
    print(f"✨ البوت يعمل على {len(bot.guilds)} سيرفر")
    print(f"👥 إجمالي الأعضاء: {sum(g.member_count for g in bot.guilds)}")
    
    load_data()
    bot.add_view(TicketView())
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ تمت مزامنة {len(synced)} أمر Slash")
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {e}")
    print("=" * 60)
    
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
        embed.set_image(url=member.guild.icon.url if member.guild.icon else None)
        embed.set_footer(text=f"انضم بتاريخ: {member.joined_at.strftime('%Y-%m-%d')}")
        await welcome_channel.send(content=member.mention, embed=embed)
    
    member_role = discord.utils.get(member.guild.roles, name="👤 • العضو")
    if member_role:
        await member.add_roles(member_role, reason="ترحيب تلقائي")

@bot.event
async def on_member_remove(member):
    logs_channel = discord.utils.get(member.guild.text_channels, name="📊・السجلات")
    if logs_channel:
        embed = discord.Embed(title="👋 غادر العضو", description=f"{member.mention} ({member.name})", color=ERROR_COLOR)
        embed.add_field(name="🆔 الID", value=member.id, inline=True)
        embed.add_field(name="📅 تاريخ الانضمام", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.timestamp = datetime.now()
        await logs_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    # حذف التذكرة إذا تم حذف القناة يدوياً
    if isinstance(channel, discord.TextChannel) and channel.id in tickets_by_channel:
        owner_id = tickets_by_channel[channel.id].get("owner_id")
        if owner_id and owner_id in tickets_db:
            del tickets_db[owner_id]
        del tickets_by_channel[channel.id]
        save_data()

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        embed = discord.Embed(title="❌ صلاحية مرفوضة", description="ليس لديك الصلاحيات المطلوبة.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.errors.BotMissingPermissions):
        embed = discord.Embed(title="❌ خطأ البوت", description="البوت لا يملك الصلاحيات المطلوبة.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.errors.CommandNotFound):
        embed = discord.Embed(title="❌ أمر غير موجود", description="هذا الأمر غير موجود.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        print(f"❌ خطأ غير معروف: {error}")
        embed = discord.Embed(title="❌ خطأ", description="حدث خطأ غير متوقع. تم إبلاغ فريق التطوير.", color=ERROR_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# حفظ تلقائي كل 5 دقائق
async def periodic_save():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            save_data()
            print(f"💾 تم حفظ البيانات تلقائياً في {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ خطأ في الحفظ التلقائي: {e}")
        await asyncio.sleep(300)

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 بدء تشغيل بوت ديسكورد المتكامل...")
    print("📌 تأكد من وجود ملف .env مع التوكن")
    print("=" * 60)
    
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ فشل تسجيل الدخول: التوكن غير صالح.")
    except Exception as e:
        print(f"❌ حدث خطأ فادح أثناء تشغيل البوت: {e}")

