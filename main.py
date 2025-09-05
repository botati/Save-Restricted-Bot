# WOODcraft https://github.com/SudoR2spr/Save-Restricted-Bot
# تم التعديل وإضافة نظام الاشتراكات مع تخزين MongoDB بواسطة مساعد Gemini

import os
import re
import time
import threading
import json
import asyncio
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, PeerIdInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message


# مكتبة للتعامل مع MongoDB بشكل غير متزامن
import motor.motor_asyncio

with open('config.json', 'r') as f: DATA = json.load(f)
def getenv(var): return os.environ.get(var) or DATA.get(var, None)

# --- الإعدادات والمتغيرات الأساسية ---
# !! تأكد من وضع معلوماتك الصحيحة هنا أو في متغيرات البيئة !!
API_ID = getenv("API_ID")
API_HASH = getenv("API_HASH")
BOT_TOKEN = getenv("LOL_BOT_TOKEN")
SESSION_STRING = getenv("STRING")
MONGO_URI = getenv("MONGO_URI")
OWNER_ID = getenv("OWNER_ID")
DEVELOPER_USERNAME = getenv("DEVELOPER_USERNAME")

# --- إعداد قاعدة البيانات ---
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client.JokerBotDB
premium_users_db = db.premium_users
free_users_db = db.free_users

# --- تهيئة البوت والحساب المساعد ---
bot = Client("mybot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
acc = Client("myacc", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# --- دوال مساعدة لقاعدة البيانات ---
async def is_premium(user_id: int) -> bool:
    """للتحقق إذا كان المستخدم مشتركًا"""
    return await premium_users_db.find_one({'_id': user_id}) is not None

async def get_user_usage(user_id: int) -> int:
    """للحصول على عدد استخدامات المستخدم المجاني"""
    user_data = await free_users_db.find_one({'_id': user_id})
    return user_data.get('usage', 0) if user_data else 0

async def increment_user_usage(user_id: int):
    """لزيادة عدد استخدامات المستخدم المجاني"""
    await free_users_db.update_one({'_id': user_id}, {'$inc': {'usage': 1}}, upsert=True)

# --- أوامر المالك (تفعيل وإلغاء الاشتراك) ---
@bot.on_message(filters.command("activate") & filters.user(OWNER_ID))
async def activate_user(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        await message.reply_text("⚠️ **خطأ في الاستخدام.**\n\nيرجى استخدام الأمر هكذا:\n`/activate 123456789`")
        return
    
    user_id_to_activate = int(message.command[1])
    if await is_premium(user_id_to_activate):
        await message.reply_text(f"✅ المستخدم `{user_id_to_activate}` مشترك بالفعل.")
        return
        
    await premium_users_db.update_one({'_id': user_id_to_activate}, {'$set': {'status': 'active'}}, upsert=True)
    await free_users_db.delete_one({'_id': user_id_to_activate})
    await message.reply_text(f"✨ تم تفعيل الاشتراك للمستخدم `{user_id_to_activate}` بنجاح.\n\nالآن يمكنه السحب بلا حدود.")

@bot.on_message(filters.command("deactivate") & filters.user(OWNER_ID))
async def deactivate_user(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        await message.reply_text("⚠️ **خطأ في الاستخدام.**\n\nيرجى استخدام الأمر هكذا:\n`/deactivate 123456789`")
        return

    user_id_to_deactivate = int(message.command[1])
    if not await is_premium(user_id_to_deactivate):
        await message.reply_text(f"ℹ️ المستخدم `{user_id_to_deactivate}` ليس مشتركًا أصلاً.")
        return

    await premium_users_db.delete_one({'_id': user_id_to_deactivate})
    await message.reply_text(f"🗑️ تم إلغاء اشتراك المستخدم `{user_id_to_deactivate}`.")


# --- معالج الرسائل الرئيسي ---
@bot.on_message(filters.text & filters.private)
async def save_handler(client, message: Message):
    user_id = message.from_user.id

    # التعامل مع روابط الانضمام
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        try:
            await acc.join_chat(message.text)
            await message.reply_text("تــم الانضمام بنـجـاح ✅🚀")
        except UserAlreadyParticipant:
            await message.reply_text("مـسـاعـد البـوت مـوجود فعـلا 🔥🚀")
        except InviteHashExpired:
            await message.reply_text("خـطـأ فـي رابــط الانضمام ⚠️‼️")
        except Exception as e:
            await message.reply_text(f"حدث خطأ: {e}")
        return

    # التعامل مع روابط الرسائل
    if "https://t.me/" in message.text:
        # التحقق من الاشتراك والحدود
        is_user_premium = await is_premium(user_id)
        if not is_user_premium:
            usage = await get_user_usage(user_id)
            if usage >= 5:
                await message.reply_text(f"🚫 **لقد وصلت إلى الحد الأقصى للسحب (5 رسائل).**\n\nللحصول على سحب غير محدود، يرجى التواصل مع المطور للاشتراك: @{DEVELOPER_USERNAME}")
                return

        # تحليل الرابط
        try:
            datas = message.text.split("/")
            temp = datas[-1].replace("?single", "").split("-")
            from_id = int(temp[0].strip())
            to_id = int(temp[1].strip()) if len(temp) > 1 else from_id
        except (ValueError, IndexError):
            await message.reply_text("يرجى إرسال رابط منشور صحيح. 🙏")
            return

        # بدء عملية الحفظ
        for msg_id in range(from_id, to_id + 1):
            chat_id_str = datas[4] if "t.me/c/" in message.text else datas[3]
            
            try:
                # محاولة الحفظ وإعادة التوجيه
                if "t.me/c/" in message.text:
                    chat_id = int("-100" + chat_id_str)
                    await acc.forward_messages(chat_id=user_id, from_chat_id=chat_id, message_ids=msg_id)
                else: # للقنوات العامة
                    await bot.forward_messages(chat_id=user_id, from_chat_id=chat_id_str, message_ids=msg_id)

                # زيادة العداد للمستخدم المجاني بعد كل عملية سحب ناجحة
                if not is_user_premium:
                    await increment_user_usage(user_id)
                
                await asyncio.sleep(2) # انتظار بسيط بين الرسائل

            except (PeerIdInvalid, ChannelPrivate, ValueError):
                await message.reply_text(
                    "❌ **فشل الوصول إلى الرسالة!**\n\n"
                    "السبب على الأغلب هو أن **الحساب المساعد ليس عضواً في القناة الخاصة**.\n"
                    "يرجى التأكد من إضافة الحساب المساعد إلى القناة ثم المحاولة مرة أخرى."
                )
                break # إيقاف الحلقة في حال حدوث خطأ
            except Exception as e:
                # إذا فشل التوجيه (بسبب الحماية)، استخدم الطريقة اليدوية
                if "t.me/c/" in message.text:
                    chat_id = int("-100" + chat_id_str)
                    await handle_private_manual(message, chat_id, msg_id)
                else:
                    await handle_private_manual(message, chat_id_str, msg_id)

                if not is_user_premium:
                    await increment_user_usage(user_id)
                await asyncio.sleep(2)
    else:
        await send_start(client, message)


async def handle_private_manual(message, chat_id, msg_id):
    """
    يقوم بتنزيل وإعادة رفع المحتوى يدويًا
    """
    try:
        msg = await acc.get_messages(chat_id, msg_id)
        # سيتم إضافة منطق التنزيل والرفع هنا عند الحاجة
        # حاليًا، forward_messages هي الطريقة الأكثر فعالية
        await msg.copy(message.chat.id)

    except Exception as e:
        await message.reply_text(f"حدث خطأ أثناء المعالجة اليدوية: {e}")

# أمر البدء
@bot.on_message(filters.command(["start"]))
async def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    await message.reply_photo(
        photo="https://c.top4top.io/p_3535lbyx51.png",
        caption="اهــلا عــزيـزي الـمـسـتـخدم انـا مسـاعد بــوت الـجوكـر مـن فـضـلك ارسـل رأبط الـمـنـشـور 📇.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("الـبـوت الـرئـيـسـي 🤖↪️", url="https://t.me/btt5bot")]])
    )

# --- دالة التشغيل الرئيسية ---
async def main():
    await acc.start()
    await bot.start()
    print(">>> البوت يعمل الآن...")
    await asyncio.Event().wait() # لإبقاء البوت يعمل

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("تم إيقاف البوت.")
