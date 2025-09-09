# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, 
    PeerIdInvalid, ChannelPrivate, FloodWait, MessageIdInvalid, UserBannedInChannel, UserIsBlocked
)
from pymongo import MongoClient

import time
import os
import threading
import json
import asyncio # تم استيراد المكتبة للعمليات غير المتزامنة

# --- إعدادات الإتصال ---
try:
    with open('config.json', 'r') as f:
        DATA = json.load(f)
except FileNotFoundError:
    DATA = {}

def getenv(var):
    return os.environ.get(var) or DATA.get(var, None)

bot_token = getenv("LOL_BOT_TOKEN")
api_hash = getenv("API_LOL_HASH")
api_id = getenv("API_LOL_ID")
ss = getenv("STRING")
mongo_uri = getenv("MONGO_DB_URI")
admin_id = int(getenv("ADMIN_ID"))
TRIAL_LIMIT = 100

cancel_tasks = {}

# --- ربط قاعدة البيانات ---
client = MongoClient(mongo_uri)
db = client['PaidBotDB']
bot_users_collection = db['bot_users']
subscriptions_collection = db['subscriptions'] # Collection جديد للاشتراكات

# --- إعدادات البوت والحساب المساعد ---
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
if ss:
    acc = Client("myacc", api_id=api_id, api_hash=api_hash, session_string=ss)
else:
    acc = None

# ... (كل أوامر المسؤول ودوال المساعدة `downstatus`, `upstatus`, `progress` تبقى كما هي) ...

# ------------------------------------------------------------------
# --- قسم المراقبة التلقائية (الجزء الجديد) ---
# ------------------------------------------------------------------

# هذا المعالج خاص بالحساب المساعد وليس البوت
if acc:
    @acc.on_message(filters.channel & ~filters.edited)
    async def channel_monitor(client, message):
        # نبحث في قاعدة البيانات عن كل المستخدمين الذين اشتركوا في هذه القناة
        subscribers = subscriptions_collection.find({"channel_id": message.chat.id})
        
        for sub in subscribers:
            try:
                # نقوم بإعادة توجيه الرسالة الجديدة إلى المستخدم المشترك
                await message.forward(sub["user_id"])
                
                # ننتظر قليلاً لتجنب حظر تيليجرام
                await asyncio.sleep(2) 
                
            except UserIsBlocked:
                # إذا حظر المستخدم البوت، يتم حذف اشتراكه تلقائياً
                subscriptions_collection.delete_one({"_id": sub["_id"]})
                print(f"User {sub['user_id']} blocked the bot. Subscription removed.")
            except Exception as e:
                print(f"Failed to forward to {sub['user_id']}: {e}")

# --- أوامر المراقبة الجديدة ---

@bot.on_message(filters.command("subscribe"))
async def subscribe_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("الرجاء استخدام الأمر هكذا: `/subscribe <رابط_القناة>`")
        return
    if not acc:
        await message.reply_text("عذراً، ميزة المراقبة التلقائية تتطلب تفعيل حساب مساعد من قبل المطور.")
        return
        
    channel_link = message.command[1]
    try:
        # نستخدم حساب المساعد للتحقق من القناة (خاصة لو كانت خاصة)
        chat = await acc.get_chat(channel_link)
        channel_id = chat.id
        channel_title = chat.title

        if subscriptions_collection.find_one({"user_id": message.from_user.id, "channel_id": channel_id}):
            await message.reply_text(f"أنت مشترك بالفعل في قناة **{channel_title}**.")
            return

        subscriptions_collection.insert_one({
            "user_id": message.from_user.id,
            "channel_id": channel_id,
            "channel_title": channel_title
        })
        await message.reply_text(f"✅ تم الاشتراك بنجاح في قناة **{channel_title}**.\nستصلك المنشورات الجديدة تلقائياً عند نشرها.")

    except Exception as e:
        await message.reply_text(f"🚫 فشل الاشتراك. تأكد أن الرابط صحيح وأن حساب المساعد عضو في القناة.\nالخطأ: `{e}`")

@bot.on_message(filters.command("unsubscribe"))
async def unsubscribe_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("الرجاء استخدام الأمر هكذا: `/unsubscribe <رابط_القناة>`")
        return
        
    channel_link = message.command[1]
    try:
        # يمكن استخدام البوت العادي هنا لأننا لا نحتاج صلاحيات خاصة
        chat = await bot.get_chat(channel_link)
        channel_id = chat.id
        
        result = subscriptions_collection.delete_one({"user_id": message.from_user.id, "channel_id": channel_id})
        
        if result.deleted_count > 0:
            await message.reply_text(f"✅ تم إلغاء الاشتراك من قناة **{chat.title}** بنجاح.")
        else:
            await message.reply_text("أنت غير مشترك في هذه القناة أصلاً.")

    except Exception as e:
        await message.reply_text(f"🚫 فشل إلغاء الاشتراك. تأكد أن الرابط صحيح.\nالخطأ: `{e}`")

@bot.on_message(filters.command("subscriptions"))
async def subscriptions_list(client, message):
    user_subs = list(subscriptions_collection.find({"user_id": message.from_user.id}))
    
    if not user_subs:
        await message.reply_text("أنت لست مشتركاً في أي قناة حالياً.")
        return
        
    response_text = "قنواتك المشترك بها حالياً:\n\n"
    for sub in user_subs:
        response_text += f"- **{sub.get('channel_title', 'اسم غير معروف')}** (`{sub['channel_id']}`)\n"
        
    await message.reply_text(response_text)

# ------------------------------------------------------------------
# --- نهاية قسم المراقبة التلقائية ---
# ------------------------------------------------------------------

# --- الأوامر الأساسية (help, start) تبقى كما هي ---
@bot.on_message(filters.command(["help", "get"]))
def send_help(client, message):
    help_text = """
🥇 **أهلاً بك في قائمة المساعدة!** 🥇

هذا البوت يساعدك على حفظ المحتوى من القنوات العامة والخاصة التي لا تسمح بالحفظ.

1️⃣ **لحفظ منشور واحد:**
فقط قم بإرسال رابط المنشور.
- `https://t.me/username/123`

2️⃣ **لحفظ مجموعة منشورات:**
أرسل الرابط مع تحديد نطاق الأرقام.
- `https://t.me/username/123-130`

3️⃣ **للقنوات الخاصة:**
أرسل رابط الدعوة الخاص بالقناة للبوت لينضم الحساب المساعد.
- `https://t.me/+aBcDeFgHiJkLmNoP`

🆕 **ميزة المراقبة التلقائية (جديد):**
- `/subscribe <رابط_القناة>`: لمراقبة قناة وإرسال منشوراتها الجديدة لك تلقائياً.
- `/unsubscribe <رابط_القناة>`: لإلغاء المراقبة.
- `/subscriptions`: لعرض قائمة قنواتك المراقبة.
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        disable_web_page_preview=True
    )

# --- الدالة الرئيسية لمعالجة الرسائل ---
# [تعديل] تم إضافة الأوامر الجديدة إلى قائمة التجاهل في الفلتر
@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel", "subscribe", "unsubscribe", "subscriptions"]))
def save(client, message):
    # ... (كل الكود القديم داخل هذه الدالة يبقى كما هو بدون تغيير) ...
    user_id = message.from_user.id
    
    if user_id != admin_id:
        # ... (كود التحقق من الفترة التجريبية) ...

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        # ... (كود الانضمام للقنوات) ...
        return

    elif "https://t.me/" in message.text:
        # ... (كود تحليل الرابط والسحب اليدوي) ...
        
# ... (دالة handle_private و get_message_type تبقى كما هي تماماً) ...

def handle_private(message, chatid, msgid):
    # ... (الكود القديم بدون تغيير) ...

def get_message_type(msg):
    # ... (الكود القديم بدون تغيير) ...

# --- تشغيل البوت (الطريقة الجديدة غير المتزامنة) ---
async def main():
    if acc:
        await acc.start()
        print("Helper account is running...")
    
    await bot.start()
    print("Bot is running...")
    
    await pyrogram.idle()
    
    await bot.stop()
    if acc:
        await acc.stop()

if __name__ == "__main__":
    # هذا السطر ضروري لتشغيل الدوال غير المتزامنة (async)
    asyncio.run(main())
