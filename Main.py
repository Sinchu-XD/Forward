import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import SessionPasswordNeeded

API_ID = 25024171
API_HASH = "7e709c0f5a2b8ed7d5f90a48219cffd3"
BOT_TOKEN = "7812831912:AAHh1Wiwhpkxpy4_Y_YkNDHkA1zsm3dQYx8"

os.makedirs("sessions", exist_ok=True)

bot = Client("ForwarderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

login_sessions = {}   # Temp OTP/2FA store
user_clients = {}     # Logged-in users
chat_pairs = {}       # Source: Target mapping


@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply("Send /login <your_phone_number> to log in.\n\nThen use /setchat <source_chat_id> <target_chat_id>")


@bot.on_message(filters.command("login"))
async def login_cmd(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        return await message.reply("Usage: /login <your_phone_number>")
    
    phone = args[1]
    session_name = f"sessions/{user_id}"
    client = Client(session_name, api_id=API_ID, api_hash=API_HASH)
    await client.connect()

    try:
        sent = await client.send_code(phone)
        login_sessions[user_id] = {
            "client": client,
            "phone": phone,
            "hash": sent.phone_code_hash,
            "step": "otp"
        }
        await message.reply("📨 Enter the OTP you received:")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")


@bot.on_message(filters.text & ~filters.command(["login", "start", "setchat"]))
async def otp_or_2fa(_, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    session = login_sessions.get(user_id)
    if not session:
        return

    client = session["client"]

    if session["step"] == "otp":
        try:
            await client.sign_in(session["phone"], session["hash"], message.text.strip())
            user_clients[user_id] = client
            del login_sessions[user_id]
            await message.reply("✅ Logged in successfully!")
            await client.start()
        except SessionPasswordNeeded:
            session["step"] = "2fa"
            await message.reply("🔐 Enter your 2FA password:")
        except Exception as e:
            await message.reply(f"❌ OTP Error: {e}")
    
    elif session["step"] == "2fa":
        try:
            await client.check_password(message.text.strip())
            user_clients[user_id] = client
            del login_sessions[user_id]
            await message.reply("✅ Logged in with 2FA!")
            await client.start()
        except Exception as e:
            await message.reply(f"❌ 2FA Error: {e}")


@bot.on_message(filters.command("setchat"))
async def setchat(_, message: Message):
    try:
        _, source_id, target_id = message.text.split()
        chat_pairs[int(source_id)] = int(target_id)
        await message.reply(f"✅ Now forwarding from `{source_id}` ➜ `{target_id}`")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")


# ✅ FORWARDING FUNCTION FOR ALL FUTURE MESSAGES
@bot.on_message(filters.all & ~filters.private)
async def forward_incoming(bot, message: Message):
    source_id = message.chat.id
    for user_id, client in user_clients.items():
        if source_id in chat_pairs:
            try:
                target_id = chat_pairs[source_id]
                await client.copy_message(
                    chat_id=target_id,
                    from_chat_id=source_id,
                    message_id=message.id
                )
                print(f"📤 Forwarded message from {source_id} to {target_id}")
            except Exception as e:
                print(f"❌ Failed to forward: {e}")


async def main():
    await bot.start()
    print("🤖 Bot running...")
    await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot stopped.")
        
