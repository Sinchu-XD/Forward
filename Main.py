import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from pyrogram.errors import SessionPasswordNeeded

API_ID = 25024171
API_HASH = "7e709c0f5a2b8ed7d5f90a48219cffd3"
BOT_TOKEN = "7812831912:AAHh1Wiwhpkxpy4_Y_YkNDHkA1zsmfQYx8"

bot = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

login_sessions = {}
user_clients = {}      # user_id -> Client
chat_links = {}        # user_id -> [(source_id, target_id)]

os.makedirs("sessions", exist_ok=True)

@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome!**\n\nSend `/login <phone>` to log in with your Telegram user.\nThen `/setchat <source_id> <target_id>` to copy messages.\n\n✅ Bot not needed in source chat."
    )

@bot.on_message(filters.command("login"))
async def login(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) != 2:
        return await message.reply("❌ Use: /login <phone_number>")
    
    phone = args[1]
    session_str = f"sessions/{user_id}"
    client = Client(session_str, api_id=API_ID, api_hash=API_HASH)

    if os.path.exists(session_str + ".session"):
        await client.start()
        user_clients[user_id] = client
        chat_links[user_id] = []
        return await message.reply("✅ Already logged in.")
    
    try:
        await client.connect()
        sent_code = await client.send_code(phone)
        login_sessions[user_id] = {
            "client": client,
            "phone": phone,
            "hash": sent_code.phone_code_hash,
            "step": "otp"
        }
        await message.reply("📨 Enter the OTP:")
    except Exception as e:
        await message.reply(f"❌ Error sending code: {e}")

@bot.on_message(filters.text & ~filters.command(["start", "login", "setchat"]))
async def handle_steps(_, message: Message):
    user_id = message.from_user.id
    session = login_sessions.get(user_id)
    if not session:
        return

    client = session["client"]
    text = message.text.strip()

    if session["step"] == "otp":
        try:
            await client.sign_in(session["phone"], session["hash"], text)
            user_clients[user_id] = client
            chat_links[user_id] = []
            del login_sessions[user_id]
            await message.reply("✅ Logged in!")
        except SessionPasswordNeeded:
            session["step"] = "2fa"
            await message.reply("🔐 Enter 2FA password:")
        except Exception as e:
            await message.reply(f"❌ OTP error: {e}")
    
    elif session["step"] == "2fa":
        try:
            await client.check_password(text)
            user_clients[user_id] = client
            chat_links[user_id] = []
            del login_sessions[user_id]
            await message.reply("✅ Logged in with 2FA!")
        except Exception as e:
            await message.reply(f"❌ 2FA error: {e}")

@bot.on_message(filters.command("setchat"))
async def set_chat(_, message: Message):
    user_id = message.from_user.id
    if user_id not in user_clients:
        return await message.reply("❌ You're not logged in.")

    args = message.text.split()
    if len(args) != 3:
        return await message.reply("❌ Usage: /setchat <source_chat_id> <target_chat_id>")
    
    try:
        source_id = int(args[1])
        target_id = int(args[2])
    except:
        return await message.reply("❌ Chat IDs must be numbers.")
    
    user_client = user_clients[user_id]
    chat_links[user_id].append((source_id, target_id))

    async def forward_message(client, msg: Message):
        try:
            await client.copy_message(
                chat_id=target_id,
                from_chat_id=msg.chat.id,
                message_id=msg.id
            )
            print(f"✅ Copied {msg.id} from {source_id} → {target_id}")
        except Exception as e:
            print(f"❌ Copy failed: {e}")

    user_client.add_handler(MessageHandler(forward_message, filters.chat(source_id)))
    await message.reply(f"✅ Set to copy from `{source_id}` → `{target_id}`")

async def main():
    await bot.start()
    print("🤖 Bot started.")

    # Start user sessions
    for user_id, client in user_clients.items():
        await client.start()

    # Keep bot alive
    await asyncio.get_event_loop().create_future()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Stopped.")
        
