import pyrogram
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, 
    PeerIdInvalid, ChannelPrivate, FloodWait, MessageIdInvalid, UserBannedInChannel
)
from pymongo import MongoClient
from io import BytesIO # استيراد ضروري للمعالجة في الذاكرة

import time
import os
import threading
import json

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

# --- متغيرات لتتبع الحالات ---
cancel_tasks = {}

# --- ربط قاعدة البيانات ---
client = MongoClient(mongo_uri)
db = client['PaidBotDB']
bot_users_collection = db['bot_users']

# --- إعدادات البوت والحساب المساعد ---
# [تعديل لزيادة السرعة] زيادة عدد العاملين إلى 20
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, workers=20)
if ss:
    # [تعديل لزيادة السرعة] زيادة عدد العاملين إلى 20
    acc = Client("myacc", api_id=api_id, api_hash=api_hash, session_string=ss, workers=20)
else:
    acc = None

# --- فلتر للتحقق من أن المستخدم هو المالك ---
def is_admin(_, __, message):
    return message.from_user.id == admin_id
admin_filter = filters.create(is_admin)

@bot.on_message(filters.command("cancel"))
def cancel_download(client, message):
    user_id = message.from_user.id
    cancel_tasks[user_id] = True
    message.reply_text("**سيتم إيقاف السحب المتعدد في حال تشغيله** ✅🔥")

# --- أوامر المالك ---
@bot.on_message(filters.command("authvip") & admin_filter)
def add_user(client, message):
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا: `/authvip <user_id>`")
        return
    try:
        user_id_to_add = int(message.command[1])
        bot_users_collection.update_one(
            {'user_id': user_id_to_add},
            {'$set': {'is_subscribed': True}, '$unset': {'usage_count': ''}},
            upsert=True
        )
        message.reply_text(f"تـم تفعيل الـVIP للمستخدم `{user_id_to_add}` بنـجـاح ✅🏆")
    except ValueError:
        message.reply_text("معرف المستخدم غير صالح.")

@bot.on_message(filters.command("remvip") & admin_filter)
def delete_user(client, message):
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا: `/remvip <user_id>`")
        return
    try:
        user_id_to_delete = int(message.command[1])
        result = bot_users_collection.delete_one({"user_id": user_id_to_delete})
        if result.deleted_count > 0:
            message.reply_text(f"تم حذف اشتراك المستخدم `{user_id_to_delete}` بنجاح!")
        else:
            message.reply_text("المستخدم غير موجود.")
    except ValueError:
        message.reply_text("معرف المستخدم غير صالح.")

@bot.on_message(filters.command("uservip") & admin_filter)
def list_users(client, message):
    users = bot_users_collection.find({'is_subscribed': True})
    user_list = [f"- `{user['user_id']}`" for user in users]
    if user_list:
        message.reply_text("قائمة المشتركين:\n" + "\n".join(user_list))
    else:
        message.reply_text("لا يوجد مشتركين حالياً.")

# --- دوال مساعدة لإظهار الحالة ---
def downstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile): break
    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread: txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"جــار تـنـزيــل، أنتـظـر مـن فـضـلك 🚀🔥 : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

def upstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile): break
    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread: txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"تـم التـحمـيـل، جـار الرفـع... ✅↪️ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

def progress(current, total, message, type):
    # This function is not used with in-memory downloads but kept for integrity
    try:
        with open(f'{message.id}{type}status.txt', "w") as fileup:
            fileup.write(f"{current * 100 / total:.1f}%")
    except Exception:
        pass

# --- الأوامر الأساسية ---
@bot.on_message(filters.command(["start"]))
def send_start(client, message):
    user_id = message.from_user.id
    bot_users_collection.update_one(
        {'user_id': user_id},
        {'$setOnInsert': {'is_subscribed': False, 'usage_count': 0}},
        upsert=True
    )
    bot.send_photo(
        chat_id=message.chat.id,
        photo="https://i.top4top.io/p_3538zm2ln1.png",
        caption="أهــلاً بـك عــزيـزي الـمـسـتـخدم، أنـا بــوت لحفظ المحتوى المقيد.\nفقط أرسل رابط المنشور المطلوب. 📇\nللمساعدة، استخدم الأمر /help",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("الـبـوت الـرئـيـسـي 🔥↪️", url="https://t.me/btt5bot")],
                [InlineKeyboardButton("مـن أكــون 😅✅", url="https://t.me/Q_A_66/65")]
            ]
        )
    )

@bot.on_message(filters.command(["help", "get"]))
def send_help(client, message):
    help_text = """
🥇 **أهلاً بك في قائمة المساعدة!** 🥇

هذا البوت يساعدك على حفظ المحتوى من القنوات العامة والخاصة التي لا تسمح بالحفظ.

1️⃣ **لحفظ منشور واحد:**
فقط قم بإرسال رابط المنشور.
- `https://t.me/username/123`
- `https://t.me/c/1234567890/456`

2️⃣ **لحفظ مجموعة منشورات (سحب متعدد):**
أرسل الرابط مع تحديد نطاق الأرقام بهذا الشكل (من - إلى).
- `https://t.me/username/123-130`

3️⃣ **للقنوات الخاصة:**
يجب أن ينضم الحساب المساعد للقناة أولاً. أرسل رابط الدعوة الخاص بالقناة للبوت.
- `https://t.me/+aBcDeFgHiJkLmNoP`

**ملاحظة هامة:** ‼️
- يجب أن يكون الحساب المساعد عضواً في القناة الخاصة لتتمكن من سحب المحتوى منها.

- شـكراً لاختـيارك بـوتـنـا 🥰👑
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        disable_web_page_preview=True
    )

# --- الدالة الرئيسية لمعالجة الرسائل ---
@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel"]))
def save(client, message):
    user_id = message.from_user.id
    
    # --- نظام التحقق والفترة التجريبية ---
    if user_id != admin_id:
        user_data = bot_users_collection.find_one({'user_id': user_id})
        if not user_data:
            bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
            user_data = bot_users_collection.find_one({'user_id': user_id})

        if not user_data.get('is_subscribed', False):
            usage_count = user_data.get('usage_count', 0)
            if usage_count >= TRIAL_LIMIT:
                bot.send_message(message.chat.id, "عـذراً، لقد استهلكت كامل رصيدك في التجربة المجانية.\nللحصول على اشتراك، تـواصـل مـع الـمـطور @EG_28 ✅🔥", reply_to_message_id=message.id)
                return

    # --- معالجة روابط الانضمام ---
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        if acc is None:
            bot.send_message(message.chat.id, "عذراً، يجب تفعيل حساب المساعد أولاً لاستخدام هذه الميزة.", reply_to_message_id=message.id)
            return
        try:
            acc.join_chat(message.text)
            bot.send_message(message.chat.id, "✅ تــم انـضـمام بنـجـاح. يـمكنك سحـب المنشورات الأن.", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id, "✅ مـسـاعـد البـوت مـوجود فعـلاً في هذه القناة.", reply_to_message_id=message.id)
        except InviteHashExpired:
            bot.send_message(message.chat.id, "🚫 خـطـأ: رابط الدعوة هذا منتهي الصلاحية أو غير صالح.", reply_to_message_id=message.id)
        except Exception as e:
            bot.send_message(message.chat.id, f"حدث خطأ غير متوقع أثناء محاولة الانضمام: `{e}`", reply_to_message_id=message.id)
        return

    # --- معالجة روابط السحب ---
    elif "https://t.me/" in message.text:
        try:
            datas = message.text.split("/")
            temp = datas[-1].replace("?single", "").split("-")
            fromID = int(temp[0].strip())
            toID = int(temp[1].strip()) if len(temp) > 1 else fromID
            if fromID > toID:
                message.reply_text("🚫 خطأ: يجب أن يكون رقم بداية السحب أصغر من رقم النهاية أو يساويه.", reply_to_message_id=message.id)
                return
        except (ValueError, IndexError):
            message.reply_text(
                "🚫 **صيغة الرابط غير صحيحة.**\n\nتأكد من أن الرابط بالشكل التالي:\n`https://t.me/username/123` (لمنشور واحد)\n`https://t.me/c/123456/456-460` (لمجموعة منشورات)",
                reply_to_message_id=message.id
            )
            return

        cancel_tasks[user_id] = False
        
        if user_id != admin_id:
            user_data = bot_users_collection.find_one({'user_id': user_id})
            if not user_data.get('is_subscribed', False):
                posts_in_this_request = toID - fromID + 1
                bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})

        for msgid in range(fromID, toID + 1):
            if cancel_tasks.get(user_id, False):
                bot.send_message(message.chat.id, "🛑 **تم إيقاف عملية السحب بنجاح بناءً على طلبك.**")
                cancel_tasks[user_id] = False
                break
            
            username = None
            if "https://t.me/c/" not in message.text:
                try:
                    username = datas[3]
                except IndexError:
                    pass

            try:
                if "https://t.me/c/" in message.text:
                    chatid = int("-100" + datas[4])
                    if acc is None:
                        bot.send_message(message.chat.id, "عذراً، يجب تفعيل حساب المساعد لسحب المحتوى من القنوات الخاصة.", reply_to_message_id=message.id)
                        return
                    handle_private(message, chatid, msgid)
                else:
                    msg = bot.get_messages(username, msgid)
                    bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)

            except UsernameNotOccupied:
                bot.send_message(message.chat.id, f"🚫 خطأ: المعرف `{username}` غير موجود أو غير صحيح.", reply_to_message_id=message.id)
                break 
            except ChannelPrivate:
                bot.send_message(message.chat.id, f"""عـذرا عـزيـزي المستخدم مسـاعد البـوت غـير موجود في هذا القناة/المجموعة
من فضـلك ارسـل رابـط الانضمام لتتمكن من سحب المنشورات ✅🔥""", reply_to_message_id=message.id)
                break
            except MessageIdInvalid:
                 bot.send_message(message.chat.id, f"🗑️ لم أتمكن من العثور على المنشور رقم `{msgid}`. قد يكون تم حذفه.", reply_to_message_id=message.id)
            except FloodWait as e:
                bot.send_message(message.chat.id, f"⏳ لقد تم تقييدي من تيليجرام. سأنتظر لمدة {e.value} ثانية ثم أكمل.", reply_to_message_id=message.id)
                time.sleep(e.value)
            except Exception:
                if acc:
                    try:
                        handle_private(message, username or datas[3], msgid)
                    except Exception as acc_e:
                        bot.send_message(message.chat.id, f"🚫 حدث خطأ غير متوقع أثناء سحب المنشور `{msgid}`: `{acc_e}`", reply_to_message_id=message.id)
                else:
                    bot.send_message(message.chat.id, f"🚫 فشل الوصول للمنشور `{msgid}`. قد تكون القناة خاصة وتحتاج لحساب مساعد.", reply_to_message_id=message.id)
            
            time.sleep(3)

def handle_private(message, chatid, msgid):
    try:
        msg = acc.get_messages(chatid, msgid)
    except Exception as e:
        if "Peer id invalid" in str(e):
            username = "القناة"
            try:
                username = message.text.split("/")[3]
            except IndexError:
                pass
            bot.send_message(
                message.chat.id,
                f"""🔒 هذه القناة (`{username}`) خاصة. يرجى إرسال رابط الدعوة الخاص بها أولاً لينضم حساب المساعد.""",
                reply_to_message_id=message.id
            )
        else:
            bot.send_message(message.chat.id, f"حدث خطأ غير متوقع أثناء الوصول للمنشور `{msgid}`: `{e}`", reply_to_message_id=message.id)
        return

    msg_type = get_message_type(msg)
    if "Text" == msg_type:
        bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
        return
        
    smsg = bot.send_message(message.chat.id, 'جـــار الــتحـمـيـل، انتـظر مـن فـضـلك... ✅🚀', reply_to_message_id=message.id)
    
    try:
        # --- [تعديل لزيادة السرعة] ---
        # ⚠️ خطر: قد يتعطل البوت إذا كان حجم الملف أكبر من ذاكرة السيرفر (e.g., > 400MB on Heroku)
        file_io = acc.download_media(msg, in_memory=True)
        
        # Pyrogram's in-memory download needs a filename for uploads
        file_name = "untitled"
        if getattr(msg, msg.media.value):
            file_name = getattr(msg, msg.media.value).file_name or "untitled"
        file_io.name = file_name
    
    except Exception as e:
        bot.edit_message_text(message.chat.id, smsg.id, f"🚫 فشل تحميل الملف: {e}")
        return

    # No need for threading status updates with in-memory as it's much faster
    bot.edit_message_text(message.chat.id, smsg.id, "✅ تم التحميل، جاري الرفع...")

    # The file is now an in-memory BytesIO object, not a path
    # We pass this object directly to the send methods
    try:
        if "Document" == msg_type:
            bot.send_document(message.chat.id, file_io, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
        elif "Video" == msg_type:
            bot.send_video(message.chat.id, file_io, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
        elif "Photo" == msg_type:
            bot.send_photo(message.chat.id, file_io, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
        else: # Fallback for audio, voice, etc.
            bot.send_document(message.chat.id, file_io, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
    except Exception as e:
        bot.edit_message_text(message.chat.id, smsg.id, f"🚫 فشل رفع الملف: {e}")
    finally:
        bot.delete_messages(message.chat.id, [smsg.id])

def get_message_type(msg):
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.photo: return "Photo"
    if msg.text: return "Text"
    return "Document" # Fallback for other media types

# --- تشغيل البوت ---
if __name__ == "__main__":
    if acc:
        acc.start()
        print("حساب المساعد يعمل...")
    bot.start()
    print("البوت يعمل...")
    pyrogram.idle()
    if acc:
        acc.stop()
    bot.stop()
