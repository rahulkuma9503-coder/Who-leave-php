import os
import json
import time
import logging
from datetime import datetime, timedelta

from telegram import Update, filters # <-- CHANGE 1: Import 'filters' from 'telegram'
from telegram.ext import Application, MessageHandler, ContextTypes

# Enable logging to see errors
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
SECRET_TOKEN = os.environ.get("TELEGRAM_SECRET_TOKEN")
PORT = int(os.environ.get("PORT", "8443")) # Render provides PORT, default to 8443 for local dev
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") # Render provides this

DATA_FILE = "data/users.json"
BAN_TIME_SECONDS = 300 # 5 minutes

def load_users():
    """Loads user data from the JSON file."""
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    """Saves user data to the JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Records the join time of new chat members."""
    # The new library provides a cleaner way to get the members
    for member in update.chat_member.new_chat_member:
        user = member.user
        if user.is_bot:
            continue
        logger.info(f"User {user.full_name} ({user.id}) joined chat {update.effective_chat.id}")
        
        users = load_users()
        users[user.id] = {
            "join_time": time.time(),
            "chat_id": update.effective_chat.id
        }
        save_users(users)

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks if a user left too soon and bans them if so."""
    # The new library provides a cleaner way to get the member
    member = update.chat_member.old_chat_member
    user = member.user

    if user.is_bot:
        return

    users = load_users()
    user_data = users.get(user.id)

    if not user_data:
        logger.info(f"User {user.full_name} ({user.id}) left, but was not in our records.")
        return

    join_time = user_data["join_time"]
    time_diff = time.time() - join_time

    # Clean up user record regardless of the outcome
    del users[user.id]
    save_users(users)

    if time_diff < BAN_TIME_SECONDS:
        logger.info(f"User {user.full_name} ({user.id}) left too quickly. Banning.")
        try:
            # Ban the user from the chat
            await context.bot.ban_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user.id,
                revoke_messages=True # Optional: removes all messages from the user
            )

            # Send a message to the banned user
            ban_message = (
                f"Hello {user.full_name},\n\n"
                f"You have been automatically banned from the group for leaving within 5 minutes of joining.\n\n"
                f"If you think this was a mistake, please contact the admin: @{ADMIN_USERNAME}"
            )
            await context.bot.send_message(
                chat_id=user.id,
                text=ban_message
            )

        except Exception as e:
            logger.error(f"Failed to ban user {user.id}: {e}")
    else:
        logger.info(f"User {user.full_name} ({user.id}) left after {time_diff:.2f} seconds. No action taken.")


def main():
    """Start the bot."""
    if not TOKEN or not ADMIN_USERNAME or not SECRET_TOKEN:
        logger.error("One or more environment variables are missing!")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Register handlers using the new filter syntax
    # CHANGE 2: Updated filters for chat member updates
    application.add_handler(MessageHandler(filters.ChatMember.CREATED, handle_new_members))
    application.add_handler(MessageHandler(filters.ChatMember.LEFT, handle_left_member))

    # Start the webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="bot.py", # The path part of the URL
        webhook_url=f"{WEBHOOK_URL}/bot.py",
        secret_token=SECRET_TOKEN
    )
    logger.info("Bot started and listening on webhook...")


if __name__ == "__main__":
    main()
