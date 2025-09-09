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
        time.sleep(1)
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
        time.sleep(1)
    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread: txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"تـم التـحمـيـل، جـار الرفـع... ✅↪️ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt', "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")

# ------------------------------------------------------------------
# --- قسم المراقبة التلقائية ---
# ------------------------------------------------------------------
if acc:
    @acc.on_message(filters.channel & ~filters.edited)
    async def channel_monitor(client, message):
        subscribers = subscriptions_collection.find({"channel_id": message.chat.id})
        for sub in subscribers:
            try:
                await message.forward(sub["user_id"])
                await asyncio.sleep(2)
            except UserIsBlocked:
                subscriptions_collection.delete_one({"_id": sub["_id"]})
                print(f"User {sub['user_id']} blocked the bot. Subscription removed.")
            except Exception as e:
                print(f"Failed to forward to {sub['user_id']}: {e}")

# --- أوامر المراقبة ---
@bot.on_message(filters.command("subscribe"))
async def subscribe_command(client, message):
    if not acc:
        await message.reply_text("عذراً، ميزة المراقبة التلقائية تتطلب تفعيل حساب مساعد من قبل المطور.")
        return
    if len(message.command) < 2:
        await message.reply_text("الرجاء استخدام الأمر هكذا: `/subscribe <رابط_القناة>`")
        return
    
    channel_link = message.command[1]
    try:
        chat = await acc.get_chat(channel_link)
        channel_id = chat.id
        channel_title = chat.title
        if subscriptions_collection.find_one({"user_id": message.from_user.id, "channel_id": channel_id}):
            await message.reply_text(f"أنت مشترك بالفعل في قناة **{channel_title}**.")
            return
        subscriptions_collection.insert_one({"user_id": message.from_user.id, "channel_id": channel_id, "channel_title": channel_title})
        await message.reply_text(f"✅ تم الاشتراك بنجاح في قناة **{channel_title}**.\nستصلك المنشورات الجديدة تلقائياً.")
    except Exception as e:
        await message.reply_text(f"🚫 فشل الاشتراك. تأكد أن الرابط صحيح وأن حساب المساعد عضو في القناة.\nالخطأ: `{e}`")

@bot.on_message(filters.command("unsubscribe"))
async def unsubscribe_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("الرجاء استخدام الأمر هكذا: `/unsubscribe <رابط_القناة>`")
        return
    
    channel_link = message.command[1]
    try:
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
# --- الأوامر الأساسية ---
# ------------------------------------------------------------------
@bot.on_message(filters.command(["start"]))
def send_start(client, message):
    user_id = message.from_user.id
    bot_users_collection.update_one({'user_id': user_id}, {'$setOnInsert': {'is_subscribed': False, 'usage_count': 0}}, upsert=True)
    bot.send_photo(
        chat_id=message.chat.id,
        photo="https://i.top4top.io/p_3538zm2ln1.png",
        caption="أهــلاً بـك عــزيـزي الـمـسـتـخدم، أنـا بــوت لحفظ المحتوى المقيد.\n\nفقط أرسل رابط المنشور المطلوب. 📇\nللمساعدة، استخدم الأمر /help",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("الـبـوت الـرئـيـسـي 🔥↪️", url="https://t.me/btt5bot")],
             [InlineKeyboardButton("مـن أكــون 😅✅", url="https://t.me/Q_A_66/65")]]
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
    bot.send_message(chat_id=message.chat.id, text=help_text, reply_to_message_id=message.id, disable_web_page_preview=True)

# ------------------------------------------------------------------
# --- الدالة الرئيسية لمعالجة الرسائل (تم إصلاحها) ---
# ------------------------------------------------------------------
@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel", "subscribe", "unsubscribe", "subscriptions"]))
def save(client, message):
    user_id = message.from_user.id
    
    if user_id != admin_id:
        user_data = bot_users_collection.find_one({'user_id': user_id}) or {}
        if not user_data:
            bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
        
        if not user_data.get('is_subscribed', False):
            usage_count = user_data.get('usage_count', 0)
            posts_to_download = 1
            if "https://t.me/" in message.text and "https://t.me/+" not in message.text:
                try:
                    datas = message.text.split("/")
                    temp = datas[-1].replace("?single","").split("-")
                    fromID = int(temp[0].strip())
                    toID = int(temp[1].strip()) if len(temp) > 1 else fromID
                    posts_to_download = toID - fromID + 1
                except (ValueError, IndexError):
                    pass
            
            if usage_count >= TRIAL_LIMIT:
                message.reply_text("عـذرا تـم انتهاء من التـجـربة الـمجـانـيه .\nمـن فـضـلك تـواصـل مـع الـمـطور @EG_28 ✅🔥")
                return
            if usage_count + posts_to_download > TRIAL_LIMIT:
                remaining = TRIAL_LIMIT - usage_count
                message.reply_text(f"عذراً 🚫، طلبك يتجاوز الرصيد المتبقي.\nلديك {remaining} منشور متبقي في الفترة التجريبية.")
                return

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        if acc is None:
            message.reply_text("عـذرا خـطـأ غـير مفهوم ‼️‼️")
            return
        try:
            acc.join_chat(message.text)
            message.reply_text("تــم انـضـمام بنـجـاح. يـمكنك سحـب المنشورات الأن ✅🚀")
        except UserAlreadyParticipant:
            message.reply_text("مـسـاعـد البـوت مـوجود فعـلا. يمـكنك سحـب المنشورات الأن 🔥🚀")
        except InviteHashExpired:
            message.reply_text("خـطـأ فـي رابــط الأنضـمام. ربما الرابط منتهي الصلاحية او تم حظر حساب المساعد.")
        except Exception as e:
            message.reply_text(f"خـطـأ : __{e}__")
        return

    elif "https://t.me/" in message.text:
        try:
            datas = message.text.split("/")
            temp = datas[-1].replace("?single","").split("-")
            fromID = int(temp[0].strip())
            toID = int(temp[1].strip()) if len(temp) > 1 else fromID
        except (ValueError, IndexError):
            message.reply_text("🚫 **صيغة الرابط غير صحيحة.**\nتأكد من أن الرابط بالشكل الصحيح.")
            return

        cancel_tasks[user_id] = False
        
        if user_id != admin_id:
            user_data = bot_users_collection.find_one({'user_id': user_id}) or {}
            if not user_data.get('is_subscribed', False):
                posts_in_this_request = toID - fromID + 1
                bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})
        
        for msgid in range(fromID, toID + 1):
            if cancel_tasks.get(user_id, False):
                message.reply_text("🛑 **تم إيقاف عملية السحب بنجاح بناءً على طلبك.**")
                cancel_tasks[user_id] = False
                break
            
            try:
                if "https://t.me/c/" in message.text:
                    chatid = int("-100" + datas[4])
                    if acc is None:
                        message.reply_text("هـنـاك خـطـأ فـي مسـاعد البـوت ⚠️🤖")
                        return
                    handle_private(message, chatid, msgid)
                else:
                    username = datas[3]
                    msg = bot.get_messages(username, msgid)
                    bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
            except Exception as e:
                try:
                    if acc:
                        handle_private(message, username, msgid)
                    else:
                         message.reply_text(f"حدث خطأ: {e}")
                except Exception as e2:
                    message.reply_text(f"حدث خطأ مزدوج: {e2}")
            time.sleep(3)

def handle_private(message, chatid, msgid):
    try:
        msg = acc.get_messages(chatid, msgid)
    except Exception as e:
        message.reply_text(f"🚫 فشل الوصول للمنشور `{msgid}`: `{e}`")
        return

    msg_type = get_message_type(msg)
    if msg_type == "Text":
        bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
        return
        
    smsg = bot.send_message(message.chat.id, 'جـــار الــتحـمـيـل...', reply_to_message_id=message.id)
    dosta = threading.Thread(target=lambda: downstatus(f'{message.id}downstatus.txt', smsg), daemon=True)
    dosta.start()
    
    try:
        file_path = acc.download_media(msg, progress=progress, progress_args=[message, "down"])
        if os.path.exists(f'{message.id}downstatus.txt'): os.remove(f'{message.id}downstatus.txt')
    except Exception as e:
        bot.edit_message_text(message.chat.id, smsg.id, f"🚫 فشل تحميل الملف: `{e}`")
        if os.path.exists(f'{message.id}downstatus.txt'): os.remove(f'{message.id}downstatus.txt')
        return

    upsta = threading.Thread(target=lambda: upstatus(f'{message.id}upstatus.txt', smsg), daemon=True)
    upsta.start()
    
    if msg_type == "Document":
        thumb = None
        try: thumb = acc.download_media(msg.document.thumbs[0].file_id)
        except: pass
        bot.send_document(message.chat.id, file_path, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])
        if thumb: os.remove(thumb)
    elif msg_type == "Video":
        thumb = None
        try: thumb = acc.download_media(msg.video.thumbs[0].file_id)
        except: pass
        bot.send_video(message.chat.id, file_path, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])
        if thumb: os.remove(thumb)
    elif msg_type == "Photo":
        bot.send_photo(message.chat.id, file_path, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
    else:
        bot.send_document(message.chat.id, file_path, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])
    
    if os.path.exists(file_path): os.remove(file_path)
    if os.path.exists(f'{message.id}upstatus.txt'): os.remove(f'{message.id}upstatus.txt')
    bot.delete_messages(message.chat.id, [smsg.id])

def get_message_type(msg):
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.photo: return "Photo"
    if msg.text: return "Text"
    return "Document"

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
    asyncio.run(main())
