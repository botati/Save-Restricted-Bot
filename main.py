# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient

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
TRIAL_LIMIT = 100

# --- متغيرات لتتبع الحالات ---
cancel_tasks = {}
active_downloads = set()

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

# --- أوامر البوت ---
@bot.on_message(filters.command("cancel"))
def cancel_download(client, message):
    user_id = message.from_user.id
    if user_id in active_downloads:
        cancel_tasks[user_id] = True
        message.reply_text("✅ **تم إرسال طلب الإلغاء...**\nسيتم إيقاف عملية السحب عند الرسالة التالية.")
    else:
        message.reply_text("ℹ️ **لا توجد عملية سحب نشطة لإلغائها.**")

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

def downstatus(statusfile,message):
	while True:
		if os.path.exists(statusfile): break
	time.sleep(3)
	while os.path.exists(statusfile):
		with open(statusfile,"r") as downread: txt = downread.read()
		try:
			bot.edit_message_text(message.chat.id, message.id, f"جــار تـنـزيــل أنتـظـر مـن فـضـلك 🚀🔥 : **{txt}**")
			time.sleep(10)
		except: time.sleep(5)

def upstatus(statusfile,message):
	while True:
		if os.path.exists(statusfile): break
	time.sleep(3)
	while os.path.exists(statusfile):
		with open(statusfile,"r") as upread: txt = upread.read()
		try:
			bot.edit_message_text(message.chat.id, message.id, f"تـم التـحمـيـل بنـجـاح ✅↪️ : **{txt}**")
			time.sleep(10)
		except: time.sleep(5)

def progress(current, total, message, type):
	with open(f'{message.id}{type}status.txt',"w") as fileup:
		fileup.write(f"{current * 100 / total:.1f}%")

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
        caption="اهــلا عــزيـزي الـمـسـتـخدم انـا مسـاعد بــوت الـجوكـر مـن فـضـلك ارسـل رأبط الـمـنـشـور 📇.",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("الـبـوت الـرئـيـسـي 🔥↪️", url="https://t.me/btt5bot")],
                [InlineKeyboardButton("مـن أكــون 😅✅", url="https://t.me/Q_A_66/65")]
            ]
        )
    )

@bot.on_message(filters.command(["help"]))
def send_help(client, message):
    help_text = """
🥇 أهلاً بك في قائمة المساعدة! 🥇
هـذا قـائـمـة الـجوكـر السـهـلـه و البـسـيـطة ↪️🏆
1. لـحفـظ مـنـشـور واحـد: ✅↪️
فقط قم بإرسال رابط المنشور العام أو الخاص. 
  - `https://t.me/username/123`
  - `https://t.me/c/1234567890/456`

2. لحفظ مجموعة من المنشورات ( الـسـحـب الـمـتعدد ) فقط ارسـل🚀🔥
 - /get

3. للانضمام إلى قناة خاصة:
 إذا كانت القناة خاصة، يجب أن ينضم الحساب المساعد أولاً. أرسل رابط الدعوة الخاص بالقناة للبوت.
 - `https://t.me/+aBcDeFgHiJkLmNoP`
 
4. لسحب ستوري (قصة):
 انسخ رابط الاستوري وارسله للبوت مباشرة.
 - `https://t.me/username/story/123`
 - `https://t.me/username/s/123`

**ملاحظة هامة:** ‼️
- يجب أن يكون الحساب المساعد عضواً في القناة الخاصة لتتمكن من سحب المحتوى منها.
- شـكرا عـلي اختـيارك بـوت الـجـوكر 🥰👑
    """
    bot.send_message(message.chat.id, text=help_text, reply_to_message_id=message.id, disable_web_page_preview=True)

@bot.on_message(filters.command(["get"]))
def send_get_help(client, message):
    help_text = """
  **لـتشـغـيـل السـحب الـمتـعدد تـابع الخـطواط** 🫴🏻✅
    أرسل الرابط بهذا الشكل (رقم البداية - رقم النهاية).
    - `https://t.me/username/123-130`
**و سيقوم ببـدأ سـحب المنشورات** 🚀🔥
    """
    bot.send_message(chat_id=message.chat.id, text=help_text, reply_to_message_id=message.id, disable_web_page_preview=True)

@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel"]))
def save(client, message):
    user_id = message.from_user.id
    
    if user_id != admin_id:
        user_data = bot_users_collection.find_one({'user_id': user_id})
        if not user_data:
            bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
            user_data = bot_users_collection.find_one({'user_id': user_id})

        if not user_data.get('is_subscribed', False):
            usage_count = user_data.get('usage_count', 0)
            posts_to_download = 1
            if "https://t.me/" in message.text and "https://t.me/+" not in message.text and "/story/" not in message.text and "/s/" not in message.text:
                try:
                    datas = message.text.split("/")
                    temp = datas[-1].replace("?single","").split("-")
                    fromID = int(temp[0].strip())
                    toID = int(temp[1].strip()) if len(temp) > 1 else fromID
                    posts_to_download = toID - fromID + 1
                except (ValueError, IndexError):
                    posts_to_download = 1
            
            if usage_count >= TRIAL_LIMIT:
                bot.send_message(message.chat.id, "عـذرا تـم انتهاء من التـجـربة الـمجـانـيه .\nمـن فـضـلك تـواصـل مـع الـمـطور @EG_28 ✅🔥", reply_to_message_id=message.id)
                return
            if usage_count + posts_to_download > TRIAL_LIMIT:
                remaining = TRIAL_LIMIT - usage_count
                bot.send_message(message.chat.id, f"عذراً 🚫، طلبك يتجاوز الرصيد المتبقي.\nلديك {remaining} محاولة متبقية.", reply_to_message_id=message.id)
                return

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        if acc is None:
            bot.send_message(message.chat.id, "الحساب المساعد غير مفعل.", reply_to_message_id=message.id)
            return
        try:
            acc.join_chat(message.text)
            bot.send_message(message.chat.id, "✅ تم انضمام الحساب المساعد بنجاح!", reply_to_message_id=message.id)
        except (InviteHashExpired, ValueError):
            bot.send_message(message.chat.id, "⚠️ **فشل الانضمام!**\nالسبب: رابط الدعوة منتهي الصلاحية أو تم إبطاله.", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id, "ℹ️ الحساب المساعد عضو بالفعل في هذه القناة.", reply_to_message_id=message.id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ **حدث خطأ:**\n`{e}`", reply_to_message_id=message.id)
        return

    elif "/story/" in message.text or "/s/" in message.text:
        if acc is None:
            bot.send_message(message.chat.id, "لا يمكن سحب الاستوريات بدون حساب مساعد.", reply_to_message_id=message.id)
            return
        
        smsg = bot.send_message(message.chat.id, "جاري سحب الاستوري...", reply_to_message_id=message.id)
        try:
            parts = message.text.strip().split("/")
            username = parts[-3] if "/s/" in message.text else parts[-2]
            story_id = int(parts[-1])
            
            if user_id != admin_id and not bot_users_collection.find_one({'user_id': user_id, 'is_subscribed': True}):
                bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': 1}})

            stories = acc.get_stories(username)
            story_to_download = next((s for s in stories if s.id == story_id), None)
            
            if story_to_download:
                file_path = acc.download_media(story_to_download)
                if story_to_download.video:
                    bot.send_video(message.chat.id, file_path, caption=story_to_download.caption, reply_to_message_id=message.id)
                else:
                    bot.send_photo(message.chat.id, file_path, caption=story_to_download.caption, reply_to_message_id=message.id)
                os.remove(file_path)
                smsg.delete()
            else:
                smsg.edit("لم يتم العثور على الاستوري. قد تكون قد حُذفت، منتهية الصلاحية، أو أن الرابط غير صحيح.")
        except Exception as e:
            smsg.edit(f"حدث خطأ أثناء سحب الاستوري:\n`{e}`")
        return

    elif "https://t.me/" in message.text:
        active_downloads.add(user_id)
        try:
            datas = message.text.split("/")
            temp = datas[-1].replace("?single","").split("-")
            fromID = int(temp[0].strip())
            toID = int(temp[1].strip()) if len(temp) > 1 else fromID
            
            cancel_tasks[user_id] = False
            
            if user_id != admin_id:
                user_data = bot_users_collection.find_one({'user_id': user_id})
                if not user_data.get('is_subscribed', False):
                    posts_in_this_request = toID - fromID + 1
                    bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})
            
            for msgid in range(fromID, toID+1):
                if cancel_tasks.get(user_id, False):
                    bot.send_message(message.chat.id, "🛑 **تم إيقاف عملية السحب بنجاح بناءً على طلبك.**")
                    break
                
                if "https://t.me/c/" in message.text:
                    chatid = int("-100" + datas[4])
                    if acc is None:
                        bot.send_message(message.chat.id, "الحساب المساعد غير مفعل.", reply_to_message_id=message.id)
                        return
                    handle_private(message,chatid,msgid)
                else: # Public Channel
                    username = datas[3]
                    try:
                        msg = bot.get_messages(username,msgid)
                        if '?single' not in message.text:
                            bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                        else:
                            bot.copy_media_group(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                    except Exception:
                        if acc is None:
                            bot.send_message(message.chat.id, "لا يمكن الوصول للمحتوى، الحساب المساعد غير مفعل.", reply_to_message_id=message.id)
                            return
                        try: handle_private(message, username, msgid)
                        except Exception as e: bot.send_message(message.chat.id, f"خـطـأ: __{e}__", reply_to_message_id=message.id)
                time.sleep(3)
        finally:
            if user_id in active_downloads:
                active_downloads.remove(user_id)
            if user_id in cancel_tasks:
                cancel_tasks[user_id] = False

def handle_private(message, chatid, msgid):
    try:
        msg = acc.get_messages(chatid, msgid)
    except (PeerIdInvalid, ValueError):
        bot.send_message(message.chat.id, "عـذرا، الحساب المساعد ليس عضوًا في هذه القناة. أرسل رابط الدعوة أولاً.", reply_to_message_id=message.id)
        return
    except Exception as e:
        bot.send_message(message.chat.id, f"حدث خطأ غير متوقع: __{e}__", reply_to_message_id=message.id)
        return

    msg_type = get_message_type(msg)
    if "Text" == msg_type:
        bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
        return
        
    smsg = bot.send_message(message.chat.id, 'جـــار الــتحـمـيـل...', reply_to_message_id=message.id)
    dosta = threading.Thread(target=lambda:downstatus(f'{message.id}downstatus.txt',smsg),daemon=True)
    dosta.start()
    file = acc.download_media(msg, progress=progress, progress_args=[message,"down"])
    os.remove(f'{message.id}downstatus.txt')
    
    upsta = threading.Thread(target=lambda:upstatus(f'{message.id}upstatus.txt',smsg),daemon=True)
    upsta.start()
    
    thumb = None
    try:
        if msg.video:
             thumb = acc.download_media(msg.video.thumbs[0].file_id)
        elif msg.document:
             thumb = acc.download_media(msg.document.thumbs[0].file_id)
    except Exception:
        pass

    if "Document" == msg_type:
        bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message,"up"])
    elif "Video" == msg_type:
        bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message,"up"])
    elif "Photo" == msg_type:
        bot.send_photo(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
    
    if thumb: os.remove(thumb)
    os.remove(file)
    if os.path.exists(f'{message.id}upstatus.txt'): os.remove(f'{message.id}upstatus.txt')
    bot.delete_messages(message.chat.id,[smsg.id])

def get_message_type(msg):
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.photo: return "Photo"
    if msg.text: return "Text"
    # Fallback for other types that are downloadable but not explicitly handled
    if msg.media: return "Document" 
    return None

# --- تشغيل البوت ---
bot.run()
print("Bot is running...")
