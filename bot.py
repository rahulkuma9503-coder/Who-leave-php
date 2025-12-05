import os
import json
import time
import logging

from telegram import Update
from telegram.ext import Application, ChatMemberHandler, ContextTypes

# Enable logging to see errors
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
# Note: PORT, WEBHOOK_URL, and SECRET_TOKEN are no longer needed for polling.

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

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles chat member updates. This single function will track joins and leaves.
    """
    result = update.chat_member
    user = result.new_chat_member.user
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    # Ignore bots
    if user.is_bot:
        return

    # Case 1: User joined the chat
    if old_status in ['left', 'kicked'] and new_status == 'member':
        logger.info(f"User {user.full_name} ({user.id}) joined chat {update.effective_chat.id}")
        users = load_users()
        users[user.id] = {
            "join_time": time.time(),
            "chat_id": update.effective_chat.id
        }
        save_users(users)

    # Case 2: User left the chat
    elif old_status == 'member' and new_status == 'left':
        logger.info(f"User {user.full_name} ({user.id}) left chat {update.effective_chat.id}")
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
                    revoke_messages=True
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
    if not TOKEN or not ADMIN_USERNAME:
        logger.error("TELEGRAM_BOT_TOKEN or ADMIN_USERNAME is missing!")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Register a single ChatMemberHandler to track all member changes
    application.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # Start the bot using polling
    # This is much simpler than webhooks!
    application.run_polling()
    logger.info("Bot started and is polling...")


if __name__ == "__main__":
    main()
