import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from pyrogram.errors import SessionPasswordNeeded

API_ID = 25024171
API_HASH = "7e709c0f5a2b8ed7d5f90a48219cffd3"
BOT_TOKEN = "7812831912:AAHh1Wiwhpkxpy4_Y_YkNDHkA1zsm3dQYx8"

bot = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

login_sessions = {}
user_clients = {}
chat_links = {}
os.makedirs("sessions", exist_ok=True)

@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome!**\n\nSend `/login <phone>` to log in with your Telegram user.\nThen `/setchat <source_id> <target_id> [phone]` to copy messages.\n\n✅ Bot not needed in source chat."
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
        if user_id not in user_clients:
            user_clients[user_id] = []
        user_clients[user_id].append(client)
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
            if user_id not in user_clients:
                user_clients[user_id] = []
            user_clients[user_id].append(client)
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
            if user_id not in user_clients:
                user_clients[user_id] = []
            user_clients[user_id].append(client)
            del login_sessions[user_id]
            await message.reply("✅ Logged in with 2FA!")
        except Exception as e:
            await message.reply(f"❌ 2FA error: {e}")

@bot.on_message(filters.command("setchat"))
async def set_chat(_, message: Message):
    user_id = message.from_user.id
    if user_id not in user_clients or not user_clients[user_id]:
        return await message.reply("❌ You're not logged in.")

    args = message.text.split()
    if len(args) not in [3, 4]:
        return await message.reply("❌ Usage: /setchat <source_chat_id> <target_chat_id> [phone]")

    try:
        source_id = int(args[1])
        target_id = int(args[2])
        phone = args[3] if len(args) == 4 else None
    except:
        return await message.reply("❌ Chat IDs must be numbers.")

    clients = user_clients.get(user_id, [])
    user_client = None
    if phone:
        for client in clients:
            if phone in client.name:
                user_client = client
                break
        if not user_client:
            return await message.reply("❌ No session found for that phone number.")
    else:
        user_client = clients[0]

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

    if user_id not in chat_links:
        chat_links[user_id] = []
    chat_links[user_id].append((source_id, target_id))

    user_client.add_handler(MessageHandler(forward_message, filters.chat(source_id)))
    await message.reply(f"✅ Set to copy from `{source_id}` → `{target_id}` using your session.")

@bot.on_message(filters.command("sessions"))
async def list_sessions(_, message: Message):
    user_id = message.from_user.id
    sessions = user_clients.get(user_id, [])
    if not sessions:
        return await message.reply("⚠️ You have no active sessions.")
    
    text = "**📱 Active Sessions:**\n\n"
    for i, c in enumerate(sessions, 1):
        text += f"{i}. `{c.name.split('/')[-1]}`\n"
    await message.reply(text)

@bot.on_message(filters.command("list"))
async def list_active(_, message: Message):
    user_id = message.from_user.id
    links = chat_links.get(user_id, [])

    if not links:
        return await message.reply("📭 No active forwards found.")

    text = "📋 **Active Forwards:**\n\n"
    for i, (source, target) in enumerate(links, 1):
        text += f"{i}. From `{source}` → `{target}`\n"
    await message.reply(text)

@bot.on_message(filters.command("stop"))
async def stop_forward(_, message: Message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) != 2:
        return await message.reply("❌ Usage: /stop <source_chat_id>")

    try:
        source_id = int(args[1])
    except:
        return await message.reply("❌ Invalid source chat ID.")

    if user_id not in chat_links or not chat_links[user_id]:
        return await message.reply("❌ You have no active forwards.")

    remaining_links = []
    removed = False
    if user_id in chat_links:
        for (src, tgt) in chat_links[user_id]:
            if src == source_id:
                try:
                    for client in user_clients[user_id]:
                        client.remove_handler(MessageHandler)
                    removed = True
                except Exception as e:
                    print(f"❌ Error removing handler: {e}")
            else:
                remaining_links.append((src, tgt))
    chat_links[user_id] = remaining_links

    if removed:
        await message.reply(f"🛑 Stopped forwarding from `{source_id}`")
    else:
        await message.reply("⚠️ No active handler found for that source.")

async def main():
    await bot.start()
    print("🤖 Bot started.")

    for user_id, clients in user_clients.items():
        for client in clients:
            await client.start()

    await asyncio.get_event_loop().create_future()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Stopped.")
        
