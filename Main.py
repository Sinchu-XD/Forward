from pyrogram import Client, filters
from pyrogram.types import Message, ChatMember

API_ID = 25024171  # Replace with your API ID
API_HASH = "7e709c0f5a2b8ed7d5f90a48219cffd3"
BOT_TOKEN = "7812831912:AAHh1Wiwhpkxpy4_Y_YkNDHkA1zsm3dQYx8"

app = Client("ghibli_forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_states = {}  # Tracks user input steps
chat_pairs = {}   # Maps source chat → target chat


@app.on_message(filters.command("start"))
async def start(client, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = {"step": "awaiting_source"}
    await message.reply_text("👋 Welcome! Please reply with the **source chat ID** (from which to forward).")


@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_chat_ids(client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_states:
        return  # User not in setup

    state = user_states[user_id]

    if state["step"] == "awaiting_source":
        try:
            source_id = int(message.text)
            state["source"] = source_id
            state["step"] = "awaiting_target"
            await message.reply_text("✅ Source saved! Now enter the **target chat ID** (to forward to).")
        except:
            await message.reply_text("❌ Invalid input. Please send a valid source chat ID.")

    elif state["step"] == "awaiting_target":
        try:
            target_id = int(message.text)
            source_id = state["source"]
            chat_pairs[source_id] = target_id
            del user_states[user_id]
            await message.reply_text(
                f"✅ Setup complete!\nNow forwarding messages from `{source_id}` to `{target_id}`."
            )
        except:
            await message.reply_text("❌ Invalid input. Please send a valid target chat ID.")


@app.on_message(filters.all & ~filters.private)
async def forward_messages(client, message: Message):
    source_id = message.chat.id
    if source_id in chat_pairs:
        target_id = chat_pairs[source_id]

        try:
            # Check if the bot is an admin in the source chat
            chat_member = await client.get_chat_member(source_id, "me")  # "me" is the bot's user ID

            if chat_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
                # If the bot is not an admin, notify the user and return
                await client.send_message(
                    message.chat.id, 
                    "❌ I am not an admin in the source chat. Please make me an admin to forward messages."
                )
                return

            # Proceed with forwarding the message
            await client.copy_message(
                chat_id=target_id,
                from_chat_id=source_id,
                message_id=message.id
            )

        except Exception as e:
            print(f"❌ Error copying message: {e}")
            # Optionally, notify the user of an error
            await client.send_message(
                message.chat.id,
                "❌ An error occurred while trying to forward the message. Please try again later."
            )


app.run()
