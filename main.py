# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
from datetime import datetime, timedelta

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
user_captions = {}

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
        message.reply_text("✅ **تم إرسال طلب الإلغاء...**")
    else:
        message.reply_text("ℹ️ **لا توجد عملية سحب نشطة لإلغائها.**")

@bot.on_message(filters.command("myid"))
def my_status(client, message):
    user_id = message.from_user.id
    user_data = bot_users_collection.find_one({'user_id': user_id})

    if not user_data:
        bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
        user_data = bot_users_collection.find_one({'user_id': user_id})

    is_subscribed = user_data.get('is_subscribed', False)
    expiry_date = user_data.get('expiry_date')
    
    # التحقق من انتهاء الصلاحية
    if is_subscribed and expiry_date and datetime.now() > expiry_date:
        is_subscribed = False
        bot_users_collection.update_one({'user_id': user_id}, {'$set': {'is_subscribed': False, 'usage_count': 0}})
        user_data['is_subscribed'] = False

    if is_subscribed:
        expiry_text = f"ينتهي في: {expiry_date.strftime('%Y-%m-%d')}" if expiry_date else "اشتراك دائم"
        status_text = f"👤 **حالة حسابك:**\n\n- **نوع الاشتراك:** VIP ⭐\n- **صلاحية الاشتراك:** {expiry_text}"
    else:
        usage_count = user_data.get('usage_count', 0)
        remaining = TRIAL_LIMIT - usage_count
        status_text = f"👤 **حالة حسابك:**\n\n- **نوع الاشتراك:** تجريبي 🆓\n- **الرصيد المتبقي:** {remaining if remaining > 0 else 0} / {TRIAL_LIMIT} محاولة"
    message.reply_text(status_text)

@bot.on_message(filters.command("stats") & admin_filter)
def bot_stats(client, message):
    total_users = bot_users_collection.count_documents({})
    vip_users = bot_users_collection.count_documents({'is_subscribed': True})
    trial_users = total_users - vip_users
    
    stats_text = f"📊 **إحصائيات البوت:**\n\n- **إجمالي المستخدمين:** {total_users}\n- **المشتركون (VIP):** {vip_users}\n- **مستخدمو الفترة التجريبية:** {trial_users}"
    message.reply_text(stats_text)

# --- [ميزة جديدة] أوامر الحفظ في قناة ---
@bot.on_message(filters.command("set_channel"))
def set_save_channel(client, message: Message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا:\n`/set_channel <channel_id_or_username>`\nمثال:\n`/set_channel -10012345678`\nأو\n`/set_channel @MyArchiveChannel`")
        return
    
    channel_id_str = message.command[1]
    try:
        # تحويل المعرف النصي إلى رقمي إذا أمكن
        target_chat_id = int(channel_id_str) if channel_id_str.startswith("-") else channel_id_str

        chat = bot.get_chat(target_chat_id)
        bot_member = bot.get_chat_member(chat.id, "me")

        if bot_member.status not in [pyrogram.enums.ChatMemberStatus.ADMINISTRATOR, pyrogram.enums.ChatMemberStatus.OWNER]:
             raise Exception("البوت ليس مسؤولاً في هذه القناة.")

        bot_users_collection.update_one({'user_id': user_id}, {'$set': {'target_channel': chat.id}})
        message.reply_text(f"✅ تم تعيين قناة الحفظ بنجاح إلى: **{chat.title}**")
    except Exception as e:
        message.reply_text(f"❌ **فشل تعيين القناة!**\nالسبب: `{e}`\n\nتأكد من أن المعرف صحيح وأن البوت لديه صلاحيات المسؤول في القناة.")

@bot.on_message(filters.command("reset_channel"))
def reset_save_channel(client, message: Message):
    user_id = message.from_user.id
    bot_users_collection.update_one({'user_id': user_id}, {'$unset': {'target_channel': ''}})
    message.reply_text("✅ تم إعادة تعيين وجهة الحفظ. سيتم الآن إرسال الملفات إليك هنا.")

# --- [تعديل] أمر إضافة مشترك مؤقت ---
@bot.on_message(filters.command("authvip") & admin_filter)
def add_user(client, message: Message):
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا:\n`/authvip <user_id> <days>`\nمثال لاشتراك دائم: `/authvip 12345`\nمثال لاشتراك 30 يوم: `/authvip 12345 30`")
        return
    try:
        user_id_to_add = int(message.command[1])
        days = None
        if len(message.command) > 2:
            days = int(message.command[2])
        
        update_data = {'$set': {'is_subscribed': True}, '$unset': {'usage_count': ''}}
        if days:
            expiry_date = datetime.now() + timedelta(days=days)
            update_data['$set']['expiry_date'] = expiry_date
            expiry_text = f"لمدة **{days}** يومًا."
        else:
            update_data['$unset']['expiry_date'] = "" # اشتراك دائم
            expiry_text = "**للأبد**."

        bot_users_collection.update_one({'user_id': user_id_to_add}, update_data, upsert=True)
        message.reply_text(f"تـم تفعيل الـVIP للمستخدم `{user_id_to_add}` بنـجـاح ✅🏆\nمدة الاشتراك: {expiry_text}")
    except (ValueError, IndexError):
        message.reply_text("صيغة الأمر غير صحيحة. يرجى المراجعة.")


# ... (بقية أوامر المالك مثل remvip و uservip تبقى كما هي)
# ...

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

# ... (أوامر help و get تبقى كما هي)
# ...

@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel", "myid", "stats", "setcaption", "delcaption", "set_channel", "reset_channel"]))
def save(client, message):
    user_id = message.from_user.id
    user_data = bot_users_collection.find_one({'user_id': user_id})

    if not user_data:
        bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
        user_data = bot_users_collection.find_one({'user_id': user_id})

    if user_id != admin_id:
        is_subscribed = user_data.get('is_subscribed', False)
        expiry_date = user_data.get('expiry_date')
        
        if is_subscribed and expiry_date and datetime.now() > expiry_date:
            is_subscribed = False
            bot_users_collection.update_one({'user_id': user_id}, {'$set': {'is_subscribed': False, 'usage_count': 0}})
            bot.send_message(user_id, "⚠️ **انتهى اشتراكك الـ VIP!**\nلقد تم إعادتك إلى الفترة التجريبية.")

        if not is_subscribed:
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
                    posts_to_download = 1
            
            if usage_count >= TRIAL_LIMIT:
                bot.send_message(message.chat.id, "عـذرا تـم انتهاء من التـجـربة الـمجـانـيه .\nمـن فـضـلك تـواصـل مـع الـمـطور @EG_28 ✅🔥", reply_to_message_id=message.id)
                return
            if usage_count + posts_to_download > TRIAL_LIMIT:
                remaining = TRIAL_LIMIT - usage_count
                bot.send_message(message.chat.id, f"عذراً 🚫، طلبك يتجاوز الرصيد المتبقي.\nلديك {remaining} محاولة متبقية.", reply_to_message_id=message.id)
                return

    target_chat_id = user_data.get('target_channel', user_id)

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        # ... (كود الانضمام يبقى كما هو)
        pass

    elif "https://t.me/" in message.text:
        active_downloads.add(user_id)
        try:
            datas = message.text.split("/")
            temp = datas[-1].replace("?single","").split("-")
            fromID = int(temp[0].strip())
            toID = int(temp[1].strip()) if len(temp) > 1 else fromID
            
            cancel_tasks[user_id] = False
            
            if user_id != admin_id:
                user_data_check = bot_users_collection.find_one({'user_id': user_id})
                if not user_data_check.get('is_subscribed', False):
                    posts_in_this_request = toID - fromID + 1
                    bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})
            
            for msgid in range(fromID, toID+1):
                if cancel_tasks.get(user_id, False):
                    bot.send_message(user_id, "🛑 **تم إيقاف عملية السحب بنجاح بناءً على طلبك.**")
                    break
                
                if "https://t.me/c/" in message.text:
                    chatid = int("-100" + datas[4])
                    handle_private(message, chatid, msgid, target_chat_id)
                else:
                    username = datas[3]
                    handle_private(message, username, msgid, target_chat_id)
                time.sleep(3)
        finally:
            if user_id in active_downloads: active_downloads.remove(user_id)
            if user_id in cancel_tasks: cancel_tasks[user_id] = False

def handle_private(message, chatid, msgid, target_chat_id):
    # ... (كود handle_private مع تعديل لإرسال الملفات إلى target_chat_id)
    pass

# ... (بقية الدوال الأخرى)
# ...

# --- تشغيل البوت ---
bot.run()
print("Bot is running...")# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
from datetime import datetime, timedelta

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
user_captions = {}

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
        message.reply_text("✅ **تم إرسال طلب الإلغاء...**")
    else:
        message.reply_text("ℹ️ **لا توجد عملية سحب نشطة لإلغائها.**")

@bot.on_message(filters.command("myid"))
def my_status(client, message):
    user_id = message.from_user.id
    user_data = bot_users_collection.find_one({'user_id': user_id})

    if not user_data:
        bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
        user_data = bot_users_collection.find_one({'user_id': user_id})

    is_subscribed = user_data.get('is_subscribed', False)
    expiry_date = user_data.get('expiry_date')
    
    if is_subscribed and expiry_date and datetime.now() > expiry_date:
        is_subscribed = False
        bot_users_collection.update_one({'user_id': user_id}, {'$set': {'is_subscribed': False, 'usage_count': 0}})

    if is_subscribed:
        expiry_text = f"ينتهي في: {expiry_date.strftime('%Y-%m-%d')}" if expiry_date else "اشتراك دائم"
        status_text = f"👤 **حالة حسابك:**\n\n- **نوع الاشتراك:** VIP ⭐\n- **صلاحية الاشتراك:** {expiry_text}"
    else:
        usage_count = user_data.get('usage_count', 0)
        remaining = TRIAL_LIMIT - usage_count
        status_text = f"👤 **حالة حسابك:**\n\n- **نوع الاشتراك:** تجريبي 🆓\n- **الرصيد المتبقي:** {remaining if remaining > 0 else 0} / {TRIAL_LIMIT} محاولة"
    message.reply_text(status_text)

@bot.on_message(filters.command("stats") & admin_filter)
def bot_stats(client, message):
    total_users = bot_users_collection.count_documents({})
    vip_users = bot_users_collection.count_documents({'is_subscribed': True})
    trial_users = total_users - vip_users
    
    stats_text = f"📊 **إحصائيات البوت:**\n\n- **إجمالي المستخدمين:** {total_users}\n- **المشتركون (VIP):** {vip_users}\n- **مستخدمو الفترة التجريبية:** {trial_users}"
    message.reply_text(stats_text)

@bot.on_message(filters.command("set_channel"))
def set_save_channel(client, message: Message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا:\n`/set_channel <channel_id_or_username>`\nمثال:\n`/set_channel -10012345678`\nأو\n`/set_channel @MyArchiveChannel`")
        return
    
    channel_id_str = message.command[1]
    try:
        target_chat_id = int(channel_id_str) if channel_id_str.startswith("-") else channel_id_str
        chat = bot.get_chat(target_chat_id)
        bot_member = bot.get_chat_member(chat.id, "me")
        if bot_member.status not in [pyrogram.enums.ChatMemberStatus.ADMINISTRATOR, pyrogram.enums.ChatMemberStatus.OWNER]:
             raise Exception("البوت ليس مسؤولاً في هذه القناة.")

        bot_users_collection.update_one({'user_id': user_id}, {'$set': {'target_channel': chat.id}})
        message.reply_text(f"✅ تم تعيين قناة الحفظ بنجاح إلى: **{chat.title}**")
    except Exception as e:
        message.reply_text(f"❌ **فشل تعيين القناة!**\nالسبب: `{e}`\n\nتأكد من أن المعرف صحيح وأن البوت لديه صلاحيات المسؤول في القناة.")

@bot.on_message(filters.command("reset_channel"))
def reset_save_channel(client, message: Message):
    user_id = message.from_user.id
    bot_users_collection.update_one({'user_id': user_id}, {'$unset': {'target_channel': ''}})
    message.reply_text("✅ تم إعادة تعيين وجهة الحفظ. سيتم الآن إرسال الملفات إليك هنا.")

@bot.on_message(filters.command("authvip") & admin_filter)
def add_user(client, message: Message):
    if len(message.command) < 2:
        message.reply_text("الرجاء استخدام الأمر هكذا:\n`/authvip <user_id> <days>`\nمثال لاشتراك دائم: `/authvip 12345`\nمثال لاشتراك 30 يوم: `/authvip 12345 30`")
        return
    try:
        user_id_to_add = int(message.command[1])
        days = None
        if len(message.command) > 2:
            days = int(message.command[2])
        
        update_data = {'$set': {'is_subscribed': True}, '$unset': {'usage_count': ''}}
        if days:
            expiry_date = datetime.now() + timedelta(days=days)
            update_data['$set']['expiry_date'] = expiry_date
            expiry_text = f"لمدة **{days}** يومًا."
        else:
            update_data['$unset']['expiry_date'] = ""
            expiry_text = "**للأبد**."

        bot_users_collection.update_one({'user_id': user_id_to_add}, update_data, upsert=True)
        message.reply_text(f"تـم تفعيل الـVIP للمستخدم `{user_id_to_add}` بنـجـاح ✅🏆\nمدة الاشتراك: {expiry_text}")
    except (ValueError, IndexError):
        message.reply_text("صيغة الأمر غير صحيحة. يرجى المراجعة.")

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
    user_list = [f"- `{user.get('user_id')}` (ينتهي في: {user.get('expiry_date', 'دائم').strftime('%Y-%m-%d') if isinstance(user.get('expiry_date'), datetime) else 'دائم'})" for user in users]
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
		try: bot.edit_message_text(message.chat.id, message.id, f"جــار تـنـزيــل... **{txt}**")
		except: time.sleep(5)

def upstatus(statusfile,message):
	while True:
		if os.path.exists(statusfile): break
	time.sleep(3)
	while os.path.exists(statusfile):
		with open(statusfile,"r") as upread: txt = upread.read()
		try: bot.edit_message_text(message.chat.id, message.id, f"جــار الرفــع... **{txt}**")
		except: time.sleep(5)

def progress(current, total, message, type):
	with open(f'{message.id}{type}status.txt',"w") as fileup:
		fileup.write(f"{current * 100 / total:.1f}%")

@bot.on_message(filters.command(["start"]))
def send_start(client, message):
    user_id = message.from_user.id
    bot_users_collection.update_one({'user_id': user_id},{'$setOnInsert': {'is_subscribed': False, 'usage_count': 0}},upsert=True)
    bot.send_photo(
        chat_id=message.chat.id,
        photo="https://i.top4top.io/p_3538zm2ln1.png",
        caption="اهــلا بك في بوت حفظ المحتوى المقيد.",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("الـبـوت الـرئـيـسـي 🔥↪️", url="https://t.me/btt5bot")],
             [InlineKeyboardButton("مـن أكــون 😅✅", url="https://t.me/Q_A_66/65")]]
        )
    )

@bot.on_message(filters.command(["help"]))
def send_help(client, message):
    help_text = "..." # محتوى رسالة المساعدة
    bot.send_message(message.chat.id, text=help_text, reply_to_message_id=message.id, disable_web_page_preview=True)

@bot.on_message(filters.command(["get"]))
def send_get_help(client, message):
    help_text = "..." # محتوى رسالة المساعدة
    bot.send_message(chat_id=message.chat.id, text=help_text, reply_to_message_id=message.id, disable_web_page_preview=True)

@bot.on_message(filters.text & ~filters.command(["start", "help", "get", "authvip", "remvip", "uservip", "cancel", "myid", "stats", "set_channel", "reset_channel"]))
def save(client, message):
    user_id = message.from_user.id
    user_data = bot_users_collection.find_one({'user_id': user_id})
    if not user_data:
        bot_users_collection.insert_one({'user_id': user_id, 'is_subscribed': False, 'usage_count': 0})
        user_data = bot_users_collection.find_one({'user_id': user_id})

    if user_id != admin_id:
        is_subscribed = user_data.get('is_subscribed', False)
        expiry_date = user_data.get('expiry_date')
        if is_subscribed and expiry_date and datetime.now() > expiry_date:
            is_subscribed = False
            bot_users_collection.update_one({'user_id': user_id}, {'$set': {'is_subscribed': False, 'usage_count': 0}})
            bot.send_message(user_id, "⚠️ **انتهى اشتراكك الـ VIP!**\nلقد تم إعادتك إلى الفترة التجريبية.")
        if not is_subscribed:
            usage_count = user_data.get('usage_count', 0)
            posts_to_download = 1
            if "https://t.me/" in message.text and "https://t.me/+" not in message.text:
                try:
                    datas = message.text.split("/")
                    temp = datas[-1].replace("?single","").split("-"); fromID = int(temp[0].strip())
                    toID = int(temp[1].strip()) if len(temp) > 1 else fromID
                    posts_to_download = toID - fromID + 1
                except (ValueError, IndexError): posts_to_download = 1
            if usage_count >= TRIAL_LIMIT:
                bot.send_message(message.chat.id, "انتهت تجربتك المجانية. تواصل مع المطور للاشتراك.", reply_to_message_id=message.id)
                return
            if usage_count + posts_to_download > TRIAL_LIMIT:
                remaining = TRIAL_LIMIT - usage_count
                bot.send_message(message.chat.id, f"طلبك يتجاوز الرصيد المتبقي ({remaining} محاولة).", reply_to_message_id=message.id)
                return

    target_chat_id = user_data.get('target_channel', user_id)

    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        # ... (كود الانضمام للقنوات)
        pass
    elif "https://t.me/" in message.text:
        active_downloads.add(user_id)
        try:
            datas = message.text.split("/"); temp = datas[-1].replace("?single","").split("-")
            fromID = int(temp[0].strip()); toID = int(temp[1].strip()) if len(temp) > 1 else fromID
            cancel_tasks[user_id] = False
            if user_id != admin_id:
                user_data_check = bot_users_collection.find_one({'user_id': user_id})
                if not user_data_check.get('is_subscribed', False):
                    posts_in_this_request = toID - fromID + 1
                    bot_users_collection.update_one({'user_id': user_id}, {'$inc': {'usage_count': posts_in_this_request}})
            for msgid in range(fromID, toID+1):
                if cancel_tasks.get(user_id, False):
                    bot.send_message(user_id, "🛑 **تم إيقاف السحب.**"); break
                if "https://t.me/c/" in message.text:
                    chatid = int("-100" + datas[4])
                    handle_private(message, chatid, msgid, target_chat_id)
                else:
                    username = datas[3]
                    handle_private(message, username, msgid, target_chat_id)
                time.sleep(3)
        finally:
            if user_id in active_downloads: active_downloads.remove(user_id)
            if user_id in cancel_tasks: cancel_tasks[user_id] = False

def handle_private(message, chatid, msgid, target_chat_id):
    # ... (كود handle_private)
    pass

def get_message_type(msg):
    # ... (كود get_message_type)
    pass

bot.run()
print("Bot is running...")
