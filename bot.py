import os
import json
import time
import logging

from telegram import Update
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

# Enable logging to see errors
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")

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

# --- NEW: Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user = update.effective_user
    # This line will now appear in your logs if the command is received
    logger.info(f"RECEIVED /start command from User {user.full_name} ({user.id}).") 
    
    await update.message.reply_html(
        f"Hello {user.mention_html()}! 👋\n\n"
        f"I am a bot that manages group memberships. "
        f"I will automatically ban users who leave a group within 5 minutes of joining.\n\n"
        f"If you have any issues, please contact my admin: @{ADMIN_USERNAME}\n\n"
        f"Use /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "Here are the available commands:\n\n"
        "/start - Welcome message and bot info.\n"
        "/help - Shows this help message.\n\n"
        "To use me, add me to your group as an administrator with the 'Ban Users' permission."
    )

# --- Existing Chat Member Handler ---

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles chat member updates with extensive logging.
    """
    result = update.chat_member
    user = result.new_chat_member.user
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    chat_id = update.effective_chat.id

    # Ignore bots
    if user.is_bot:
        logger.info(f"Ignoring bot event for {user.full_name} in chat {chat_id}")
        return

    logger.info(f"Chat member update in {chat_id}: User {user.full_name} ({user.id}) changed from {old_status} to {new_status}")

    # Case 1: User joined the chat
    if old_status in ['left', 'kicked'] and new_status == 'member':
        logger.info(f"-> User {user.full_name} ({user.id}) JOINED. Recording join time.")
        users = load_users()
        users[user.id] = {
            "join_time": time.time(),
            "chat_id": chat_id
        }
        save_users(users)
        logger.info(f"-> User {user.id} recorded in data file.")

    # Case 2: User left the chat
    elif old_status == 'member' and new_status == 'left':
        logger.info(f"-> User {user.full_name} ({user.id}) LEFT. Checking for ban eligibility.")
        users = load_users()
        user_data = users.get(user.id)

        if not user_data:
            logger.warning(f"-> User {user.id} left, but was NOT found in our records. No action taken.")
            return

        join_time = user_data["join_time"]
        time_diff = time.time() - join_time
        logger.info(f"-> User {user.id} was in the group for {time_diff:.2f} seconds.")

        # Clean up user record regardless of the outcome
        del users[user.id]
        save_users(users)
        logger.info(f"-> User {user.id} removed from data file.")

        if time_diff < BAN_TIME_SECONDS:
            logger.info(f"-> Time difference is less than {BAN_TIME_SECONDS}s. Proceeding with ban.")
            try:
                await context.bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                    revoke_messages=True
                )
                logger.info(f"-> SUCCESS: Banned user {user.id}.")

                ban_message = (
                    f"Hello {user.full_name},\n\n"
                    f"You have been automatically banned from the group for leaving within 5 minutes of joining.\n\n"
                    f"If you think this was a mistake, please contact the admin: @{ADMIN_USERNAME}"
                )
                await context.bot.send_message(
                    chat_id=user.id,
                    text=ban_message
                )
                logger.info(f"-> Sent ban notification message to user {user.id}.")

            except Exception as e:
                logger.error(f"-> FAILED to ban user {user.id}. Error: {e}")
        else:
            logger.info(f"-> Time difference is greater than {BAN_TIME_SECONDS}s. No ban needed.")
    else:
        logger.info(f"-> Member status change not relevant for join/leave logic.")

def main():
    """Start the bot."""
    if not TOKEN or not ADMIN_USERNAME:
        logger.error("TELEGRAM_BOT_TOKEN or ADMIN_USERNAME is missing!")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # --- Register Handlers ---

    # Register command handlers for direct messages to the bot
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Register the chat member handler for group updates
    application.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # Start the bot using polling
    application.run_polling()
    logger.info("Bot started and is polling...")


if __name__ == "__main__":
    main()
