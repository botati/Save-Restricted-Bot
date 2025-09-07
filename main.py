# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
from pyrogram.enums import ParseMode

import time
import os
import threading
import json

# --- إعدادات الإتصال ---
with open('config.json', 'r') as f: DATA = json.load(f)
def getenv(var): return os.environ.get(var) or DATA.get(var, None)

bot_token = getenv("LOL_BOT_TOKEN")
api_hash = getenv("API_LOL_HASH")
api_id = getenv("API_LOL_ID")
ss = getenv("STRING")
mongo_uri = getenv("MONGO_DB_URI")
admin_id = int(getenv("ADMIN_ID"))
TRIAL_LIMIT = 20

# --- متغيرات جديدة لتتبع الإلغاء وصورة الغلاف ---
cancel_tasks = {}
user_thumbnails = {}  # <-- [جديد] لتخزين صور الغلاف المؤقتة لكل مستخدم

# --- ربط قاعدة البيانات ---
client = MongoClient(mongo_uri)
db = client['PaidBotDB']
bot_users_collection = db['bot_users']

# --- إعدادات البوت والحساب المساعد ---
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
if ss:
    acc = Client("myacc", api_id=api_id, api_hash=api_hash, session_string=ss)
    acc.start()
else:
    acc = None

# --- فلتر للتحقق من أن المستخدم هو المالك ---
def is_admin(_, __, message):
    return message.from_user.id == admin_id
admin_filter = filters.create(is_admin)

# --- [جديد] أوامر للتحكم في صورة الغلاف المخصصة ---
@bot.on_message(filters.command("setthumb"))
def set_thumbnail(client, message: Message):
    user_id = message.from_user.id
    if message.reply_to_message and message.reply_to_message.photo:
        # حفظ معرف الصورة في القاموس
        user_thumbnails[user_id] = message.reply_to_message.photo.file_id
        message.reply_text("✅ **تم حفظ صورة الغلاف بنجاح!**\nسيتم تطبيقها على الفيديوهات القادمة.")
    else:
        message.reply_text("⚠️ **خطأ!**\nيرجى الرد على صورة باستخدام الأمر `/setthumb` لتعيينها كغلاف.")

@bot.on_message(filters.command("delthumb"))
def delete_thumbnail(client, message: Message):
    user_id = message.from_user.id
    if user_id in user_thumbnails:
        del user_thumbnails[user_id]
        message.reply_text("🗑️ **تم حذف صورة الغلاف المخصصة.**\nسيتم الآن استخدام الأغلفة الأصلية.")
    else:
        message.reply_text("ℹ️ لم تقم بتعيين أي صورة غلاف مخصصة.")

# ... (بقية الأوامر الأخرى تبقى كما هي)
@bot.on_message(filters.command("cancel"))
def cancel_download(client, message):
    user_id = message.from_user.id
    cancel_tasks[user_id] = True
    message.reply_text("✅ **تم إرسال طلب الإلغاء...**\nسيتم إيقاف عملية السحب عند الرسالة التالية.")

# --- الدالة الرئيسية لمعالجة الرسائل ---
@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "adduser", "deluser", "users", "cancel", "setthumb", "delthumb"]))
def save(client, message):
    # ... (كود التحقق من المستخدم والرصيد يبقى كما هو)
    pass
# ... (بقية الكود الأساسي يبقى كما هو)

# --- [تعديل] دالة معالجة القنوات الخاصة ---
def handle_private(message, chatid, msgid):
    user_id = message.from_user.id # <-- [جديد] نحصل على معرف المستخدم
    try:
        msg = acc.get_messages(chatid, msgid)
    except Exception as e:
        bot.send_message(message.chat.id, f"حدث خطأ: {e}", reply_to_message_id=message.id)
        return

    msg_type = get_message_type(msg)

    if msg_type == "Video":
        smsg = bot.send_message(message.chat.id, 'جـــار الــتـحـمـيـل ✅🚀', reply_to_message_id=message.id)
        file = acc.download_media(msg)
        
        custom_thumb_path = None
        # --- [تعديل] التحقق من وجود غلاف مخصص وتنزيله ---
        if user_id in user_thumbnails:
            try:
                # تنزيل الغلاف المخصص
                custom_thumb_path = bot.download_media(user_thumbnails[user_id])
            except Exception as e:
                print(f"Failed to download custom thumb: {e}")
                custom_thumb_path = None # العودة للوضع الافتراضي عند الفشل
        
        # إذا لم يكن هناك غلاف مخصص، استخدم الغلاف الأصلي إن وجد
        original_thumb_path = None
        if not custom_thumb_path:
            try:
                original_thumb_path = acc.download_media(msg.video.thumbs[0].file_id)
            except:
                pass

        # اختيار المسار الصحيح للغلاف
        final_thumb_path = custom_thumb_path or original_thumb_path

        bot.send_video(
            message.chat.id,
            file,
            thumb=final_thumb_path, # <-- [تعديل] استخدام الغلاف النهائي
            caption=msg.caption,
            reply_to_message_id=message.id
        )
        
        bot.delete_messages(message.chat.id, [smsg.id])
        os.remove(file)
        # حذف ملفات الغلاف بعد الاستخدام
        if custom_thumb_path: os.remove(custom_thumb_path)
        if original_thumb_path: os.remove(original_thumb_path)
        
    elif msg_type: # معالجة الأنواع الأخرى من الرسائل
        # ... (كود معالجة الملفات الأخرى يبقى كما هو)
        pass

# ... (بقية الدوال الأخرى تبقى كما هي)
def get_message_type(msg):
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.animation: return "Animation"
    if msg.sticker: return "Sticker"
    if msg.voice: return "Voice"
    if msg.audio: return "Audio"
    if msg.photo: return "Photo"
    if msg.text: return "Text"
    return None

# --- تشغيل البوت ---
bot.run()
print("Bot is running...")
