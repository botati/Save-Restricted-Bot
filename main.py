# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
TRIAL_LIMIT = 20  # الحد الأقصى للمنشورات في الفترة التجريبية

# --- ربط قاعدة البيانات ---
client = MongoClient(mongo_uri)
db = client['PaidBotDB']
# تم تغيير اسم الـ collection ليعكس الهيكل الجديد
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


# help command
@bot.on_message(filters.command(["help"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    help_text = """
   🥇 **أهلاً بك في قائمة المساعدة!** 🥇

    هـذا قـائـمـة الـجوكـر السـهـلـه و البـسـيـطة ↪️🏆

     🚀 **1. لـحفـظ مـنـشـور واحـد:**
     فقط قم بإرسال رابط المنشور العام أو الخاص. 
    - `https://t.me/username/123`
    - `https://t.me/c/1234567890/456`

   **2. لحفظ مجموعة من المنشورات ( الـسـحـب الـمـتعدد **  فقط ارسـل🚀🔥
   
    - /get

    **3. للانضمام إلى قناة خاصة:**
    إذا كانت القناة خاصة، يجب أن ينضم الحساب المساعد أولاً. أرسل رابط الدعوة الخاص بالقناة للبوت.
    - `https://t.me/+aBcDeFgHiJkLmNoP`

    **ملاحظة هامة:** ‼️
    - يجب أن يكون الحساب المساعد عضواً في القناة الخاصة لتتمكن من سحب المحتوى منها.
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        disable_web_page_preview=True
    )
	
	

@bot.on_message(filters.command(["get"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    help_text = """
  **لـتشـغـيـل السـحب الـمتـعدد تـابع الخـطواط** 🫴🏻✅
    أرسل الرابط بهذا الشكل (رقم البداية - رقم النهاية).
    - `https://t.me/username/123-130`
**و سيقوم ببـدأ سـحب المنشورات** 🚀🔥
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        disable_web_page_preview=True
    )

# --- أوامر المالك للتحكم في المشتركين (تم تحديثها) ---
@bot.on_message(filters.command("adduser") & admin_filter)
def add_user(client, message):
    if len(message.command) < 2:
        message.reply_text(
            "الرجاء استخدام الأمر هكذا: `/adduser USER_ID`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        user_id_to_add = int(message.command[1])
        # تحديث المستخدم أو إضافته كمشترك دائم
        bot_users_collection.update_one(
            {'user_id': user_id_to_add},
            {'$set': {'is_subscribed': True}, '$unset': {'usage_count': ''}},
            upsert=True
        )
        message.reply_text(f"تم ترقية المستخدم `{user_id_to_add}` إلى مشترك دائم! 🎉")
    except ValueError:
        message.reply_text("معرف المستخدم غير صالح.")
    except Exception as e:
        message.reply_text(f"حدث خطأ: {e}")

@bot.on_message(filters.command("deluser") & admin_filter)
def delete_user(client, message):
    if len(message.command) < 2:
        message.reply_text(
            "الرجاء استخدام الأمر هكذا: `/deluser USER_ID`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        user_id_to_delete = int(message.command[1])
        result = bot_users_collection.delete_one({"user_id": user_id_to_delete})
        if result.deleted_count > 0:
            message.reply_text(f"تم حذف المستخدم `{user_id_to_delete}` بنجاح! 🗑️")
        else:
            message.reply_text("المستخدم غير موجود.")
    except ValueError:
        message.reply_text("معرف المستخدم غير صالح.")

@bot.on_message(filters.command("users") & admin_filter)
def list_users(client, message):
    # عرض المشتركين الدائمين فقط
    users = bot_users_collection.find({'is_subscribed': True})
    user_list = [f"- `{user['user_id']}`" for user in users]
    if user_list:
        message.reply_text("قائمة المشتركين الدائمين:\n" + "\n".join(user_list))
    else:
        message.reply_text("لا يوجد مشتركين دائمين حالياً.")

# --- الأكواد الأساسية للبوت (بدون تغيير) ---
def downstatus(statusfile,message):
	while True:
		if os.path.exists(statusfile): break
	time.sleep(3)
	while os.path.exists(statusfile):
		with open(statusfile,"r") as downread: txt = downread.read()
		try:
			bot.edit_message_text(message.chat.id, message.id, f"تـم تـنـزيــل بنـجـاح ✅ : **{txt}**")
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
    # إضافة المستخدم الجديد إلى قاعدة البيانات إذا لم يكن موجودًا
    bot_users_collection.update_one(
        {'user_id': user_id},
        {'$setOnInsert': {'is_subscribed': False, 'usage_count': 0}},
        upsert=True
    )
    bot.send_photo(
        chat_id=message.chat.id,
        photo="https://c.top4top.io/p_3535lbyx51.png",
        caption="اهــلا عــزيـزي الـمـسـتـخدم انـا مسـاعد بــوت الـجوكـر مـن فـضـلك ارسـل رأبط الـمـنـشـور 📇.",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("الـبـوت الـرئـيـسـي 🤖↪️", url="https://t.me/btt5bot")]])
    )

# --- بقية الأوامر مثل help و get تبقى كما هي ---
# ... (الكود الخاص بأوامر help و get) ...

@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "adduser", "deluser", "users"]))
def save(client, message):
    user_id = message.from_user.id
    
    # --- نظام التحقق الجديد مع الفترة التجريبية ---
    if user_id != admin_id:
        user_data = bot_users_collection.find_one({'user_id': user_id})

        # إذا لم يكن المستخدم موجودًا (لأمان إضافي)، قم بإضافته
        if not user_data:
            bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
            user_data = bot_users_collection.find_one({'user_id': user_id})

        # إذا كان المستخدم مشتركًا، اسمح له بالمرور
        if user_data.get('is_subscribed', False):
            pass
        # إذا لم يكن مشتركًا، تحقق من الرصيد
        else:
            usage_count = user_data.get('usage_count', 0)
            
            # حساب عدد المنشورات المطلوبة في هذه المرة
            posts_to_download = 0
            if "https://t.me/" in message.text:
                try:
                    datas = message.text.split("/")
                    temp = datas[-1].replace("?single","").split("-")
                    fromID = int(temp[0].strip())
                    toID = int(temp[1].strip()) if len(temp) > 1 else fromID
                    posts_to_download = toID - fromID + 1
                except (ValueError, IndexError):
                    posts_to_download = 1 # افتراض أنه منشور واحد إذا فشل التحليل

            if usage_count >= TRIAL_LIMIT:
                bot.send_message(message.chat.id, f"لقد استهلكت رصيدك التجريبي ({TRIAL_LIMIT} منشور).\nللاستمرار في استخدام البوت، يرجى التواصل مع المالك للاشتراك.", reply_to_message_id=message.id)
                return

            if usage_count + posts_to_download > TRIAL_LIMIT:
                remaining = TRIAL_LIMIT - usage_count
                bot.send_message(message.chat.id, f"عذراً 🚫، طلبك يتجاوز الرصيد المتبقي.\nلديك {remaining} منشور متبقي في الفترة التجريبية.", reply_to_message_id=message.id)
                return
    
    # --- بقية الكود الأصلي (من هنا يبدأ التنفيذ بعد التحقق) ---
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        if acc is None:
            bot.send_message(message.chat.id,f"عـذرا خـطـأ غـير مفهوم ‼️‼️", reply_to_message_id=message.id)
            return
        try:
            try: acc.join_chat(message.text)
            except Exception as e:
                bot.send_message(message.chat.id,f"خـطـأ : __{e}__", reply_to_message_id=message.id)
                return
            bot.send_message(message.chat.id,"تــم انـضـمام بنـجـاح ✅🚀", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id,"مـسـاعـد البـوت مـوجود فعـلا 🔥🚀", reply_to_message_id=message.id)
        except InviteHashExpired:
            bot.send_message(message.chat.id,"خـطـأ فـي رابــط الأنضـمام ⚠️‼️", reply_to_message_id=message.id)

    elif "https://t.me/" in message.text:
        datas = message.text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try: toID = int(temp[1].strip())
        except: toID = fromID
        
        # زيادة عداد الاستخدام للمستخدمين غير المشتركين
        if user_id != admin_id:
            user_data = bot_users_collection.find_one({'user_id': user_id})
            if not user_data.get('is_subscribed', False):
                 posts_in_this_request = toID - fromID + 1
                 bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})

        for msgid in range(fromID, toID+1):
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                if acc is None:
                    bot.send_message(message.chat.id,f"هـنـاك خـطـأ فـي مسـاعد البـوت ⚠️🤖", reply_to_message_id=message.id)
                    return
                handle_private(message,chatid,msgid)
            # ... (بقية كود السحب يبقى كما هو)
            else:
                username = datas[3]
                try: msg = bot.get_messages(username,msgid)
                except UsernameNotOccupied:
                    bot.send_message(message.chat.id,f"عـذرا هـذا الـمـجمـوعـة / الـقـناة غـير مـوجـوده مـن فضـلك حـاول مـن جـديد ✅🚀", reply_to_message_id=message.id)
                    return
                try:
                    if '?single' not in message.text:
                        bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                    else:
                        bot.copy_media_group(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                except:
                    if acc is None:
                        bot.send_message(message.chat.id,f"هـنـاك خـطـأ فـي مسـاعد البـوت ⚠️🤖", reply_to_message_id=message.id)
                        return
                    try: handle_private(message,username,msgid)
                    except Exception as e: bot.send_message(message.chat.id,f"خـطـأ : __{e}__", reply_to_message_id=message.id)
            time.sleep(3)

# ... (بقية الدوال handle_private, get_message_type تبقى كما هي)
def handle_private(message, chatid, msgid):
    try:
        msg = acc.get_messages(chatid, msgid)
    except (PeerIdInvalid, ChannelPrivate, ValueError):
        bot.send_message(message.chat.id, "❌ **فشل الوصول إلى الرسالة!**...", reply_to_message_id=message.id)
        return
    except Exception as e:
        bot.send_message(message.chat.id, f"حدث خطأ غير متوقع: __{e}__", reply_to_message_id=message.id)
        return

    msg_type = get_message_type(msg)
    if "Text" == msg_type:
        bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
        return
    smsg = bot.send_message(message.chat.id, 'جـــار الــتـحـمـيـل ✅🚀', reply_to_message_id=message.id)
    dosta = threading.Thread(target=lambda:downstatus(f'{message.id}downstatus.txt',smsg),daemon=True)
    dosta.start()
    file = acc.download_media(msg, progress=progress, progress_args=[message,"down"])
    os.remove(f'{message.id}downstatus.txt')
    upsta = threading.Thread(target=lambda:upstatus(f'{message.id}upstatus.txt',smsg),daemon=True)
    upsta.start()
    if "Document" == msg_type:
        try: thumb = acc.download_media(msg.document.thumbs[0].file_id)
        except: thumb = None
        bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message,"up"])
        if thumb != None: os.remove(thumb)
    elif "Video" == msg_type:
        try: thumb = acc.download_media(msg.video.thumbs[0].file_id)
        except: thumb = None
        bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message,"up"])
        if thumb != None: os.remove(thumb)
    elif "Photo" == msg_type:
        bot.send_photo(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
    os.remove(file)
    if os.path.exists(f'{message.id}upstatus.txt'): os.remove(f'{message.id}upstatus.txt')
    bot.delete_messages(message.chat.id,[smsg.id])

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
