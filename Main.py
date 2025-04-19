import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import SessionPasswordNeeded

API_ID = 12345678  # Replace with your actual API ID
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_here"

os.makedirs("sessions", exist_ok=True)

bot = Client("ForwarderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

login_sessions = {}   # Temp store for OTP/2FA flow
user_clients = {}     # user_id: pyrogram.Client
chat_pairs = {}       # source_id: target_id


@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply("Send `/login <your_phone>` to log in (if not already).\nThen use `/setchat <source_chat_id> <target_chat_id>`.")


@bot.on_message(filters.command("login"))
async def login_cmd(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        return await message.reply("Usage: /login <your_phone_number>")

    phone = args[1]
    session_name = f"sessions/{user_id}"

    # ✅ Check if already logged in
    if os.path.exists(f"{session_name}.session"):
        client = Client(session_name, api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        try:
            await client.get_me()
            await client.start()
            user_clients[user_id] = client
            return await message.reply("✅ You are already logged in!")
        except Exception as e:
            await message.reply(f"⚠️ Error loading saved session: {e}")
            return

    # Proceed with fresh login if session doesn't exist
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
        await message.reply("📨 OTP sent. Please reply with the code.")
    except Exception as e:
        await message.reply(f"❌ Failed to send code: {e}")


@bot.on_message(filters.text & ~filters.command(["login", "start", "setchat"]))
async def otp_or_2fa(_, message: Message):
    user_id = message.from_user.id
    session = login_sessions.get(user_id)
    if not session:
        return

    client = session["client"]
    code = message.text.strip()

    if session["step"] == "otp":
        try:
            await client.sign_in(session["phone"], session["hash"], code)
            await client.start()
            user_clients[user_id] = client
            del login_sessions[user_id]
            await message.reply("✅ Logged in successfully!")
        except SessionPasswordNeeded:
            session["step"] = "2fa"
            await message.reply("🔐 Please send your 2FA password:")
        except Exception as e:
            await message.reply(f"❌ OTP Error: {e}")

    elif session["step"] == "2fa":
        try:
            await client.check_password(code)
            await client.start()
            user_clients[user_id] = client
            del login_sessions[user_id]
            await message.reply("✅ Logged in with 2FA successfully!")
        except Exception as e:
            await message.reply(f"❌ 2FA Error: {e}")


@bot.on_message(filters.command("setchat"))
async def setchat(_, message: Message):
    try:
        _, source_id, target_id = message.text.split()
        chat_pairs[int(source_id)] = int(target_id)
        await message.reply(f"🔁 Messages from `{source_id}` ➜ `{target_id}` will now be forwarded.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")


# ✅ Auto Forwarding Function
@bot.on_message(filters.all & ~filters.private)
async def forward_messages(_, message: Message):
    source_id = message.chat.id
    for user_id, client in user_clients.items():
        if source_id in chat_pairs:
            target_id = chat_pairs[source_id]
            try:
                await client.copy_message(
                    chat_id=target_id,
                    from_chat_id=source_id,
                    message_id=message.id
                )
                print(f"📤 Forwarded from {source_id} to {target_id}")
            except Exception as e:
                print(f"❌ Forward error: {e}")


async def main():
    # ✅ Auto-load all existing user sessions
    for fname in os.listdir("sessions"):
        if fname.endswith(".session"):
            user_id = fname.split(".")[0]
            try:
                client = Client(f"sessions/{user_id}", api_id=API_ID, api_hash=API_HASH)
                await client.start()
                user_clients[int(user_id)] = client
                print(f"✅ Loaded session for {user_id}")
            except Exception as e:
                print(f"⚠️ Failed to load session {user_id}: {e}")

    await bot.start()
    print("🤖 Bot running...")
    await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("👋 Exiting.")
                    
