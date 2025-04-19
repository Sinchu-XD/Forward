import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import SessionPasswordNeeded

API_ID = 25024171
API_HASH = "7e709c0f5a2b8ed7d5f90a48219cffd3"
BOT_TOKEN = "7812831912:AAHh1Wiwhpkxpy4_Y_YkNDHkA1zsm3dQYx8"

# Ensure sessions folder exists
os.makedirs("sessions", exist_ok=True)

bot = Client("ghibli_forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

login_sessions = {}  # Temporary OTP/2FA data
user_clients = {}    # Active logged-in user Clients
chat_pairs = {}      # Source → Target chat mappings


@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text("👋 Send /login <your_phone_number> to login with your Telegram account.")


@bot.on_message(filters.command("login"))
async def handle_login(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) != 2:
        await message.reply_text("📱 Please use `/login <your_phone_number>`\n\nExample: `/login +919876543210`", quote=True)
        return

    phone = args[1].strip()
    session_name = f"sessions/{user_id}"

    if os.path.exists(session_name + ".session"):
        user_clients[user_id] = Client(session_name, api_id=API_ID, api_hash=API_HASH)
        await user_clients[user_id].start()
        await message.reply_text("✅ You're already logged in.")
        return

    try:
        user_clients[user_id] = Client(session_name, api_id=API_ID, api_hash=API_HASH)
        await user_clients[user_id].connect()
        sent_code = await user_clients[user_id].send_code(phone)

        login_sessions[user_id] = {
            "client": user_clients[user_id],
            "phone": phone,
            "hash": sent_code.phone_code_hash,
            "step": "otp"
        }
        await message.reply_text("📨 Enter the OTP you received:")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


@bot.on_message(filters.text & ~filters.command(["start", "login", "setchat"]))
async def login_flow(_, message: Message):
    user_id = message.from_user.id
    session = login_sessions.get(user_id)

    if not session:
        return

    step = session["step"]
    client = session["client"]

    if step == "otp":
        try:
            await client.sign_in(
                phone_number=session["phone"],
                phone_code_hash=session["hash"],
                phone_code=message.text.strip()
            )
            del login_sessions[user_id]
            await message.reply_text("✅ Logged in successfully!")
        except SessionPasswordNeeded:
            session["step"] = "2fa"
            await message.reply_text("🔐 2FA enabled. Enter your password:")
        except Exception as e:
            await message.reply_text(f"❌ OTP Error: {e}")

    elif step == "2fa":
        try:
            await client.check_password(message.text.strip())
            del login_sessions[user_id]
            await message.reply_text("✅ Logged in with 2FA!")
        except Exception as e:
            await message.reply_text(f"❌ 2FA Error: {e}")


from pyrogram import handlers

@bot.on_message(filters.command("setchat"))
async def set_chat(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) != 3:
        return await message.reply_text("❌ Use: /setchat <source_chat_id> <target_chat_id>")

    source_id = int(args[1])
    target_id = int(args[2])

    if user_id not in user_clients:
        return await message.reply_text("❌ Please login first using /login")

    user_client = user_clients[user_id]

    async def on_source_message(_, msg: Message):
        try:
            await bot.copy_message(
                chat_id=target_id,
                from_chat_id=msg.chat.id,
                message_id=msg.id
            )
            print(f"✅ Copied from {msg.chat.id} to {target_id}")
        except Exception as e:
            print(f"❌ Copy error: {e}")

    # Create handler
    handler = handlers.MessageHandler(on_source_message, filters.chat(source_id))

    # Add to user's client
    user_client.add_handler(handler)

    await message.reply_text(f"✅ All messages from `{source_id}` will be copied to `{target_id}`.")




async def main():
    await bot.start()
    print("🤖 Bot is running.")
    await asyncio.get_event_loop().create_future()

# Start the bot
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
