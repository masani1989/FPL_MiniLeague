"""Telegram bot handlers and wiring."""
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend import db
from backend.agent import OllamaAgent


def build_telegram_app(token: str) -> Application | None:
    if not token:
        return None
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("standings", standings_command))
    app.add_handler(CommandHandler("winnings", winnings_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app


async def set_webhook_on_startup(app: Application, webhook_url: str, secret: str = "") -> None:
    """Set Telegram webhook URL if one is configured."""
    if not webhook_url:
        return
    if secret:
        await app.bot.set_webhook(url=webhook_url, secret_token=secret)
    else:
        await app.bot.set_webhook(url=webhook_url)


def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.bot.username or ""


def _is_directed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat is None:
        return False
    if update.effective_chat.type == "private":
        return True
    text = update.message.text or ""
    username = _bot_username(context)
    if username and f"@{username}" in text:
        return True
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        return True
    return False


def _strip_mention(text: str, username: str) -> str:
    return re.sub(rf"\s*@{re.escape(username)}\s*", " ", text).strip()


async def _upsert_chat(update: Update) -> dict:
    chat = update.effective_chat
    user = update.effective_user
    record = {
        "chat_id": chat.id,
        "chat_type": chat.type,
        "title": chat.title or f"{user.first_name or ''} {user.last_name or ''}".strip(),
    }
    await db.upsert_telegram_chat(record)
    return record


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _upsert_chat(update)
    await update.message.reply_text(
        "Hi! I'm the Fantasy Kings AI assistant.\n"
        "Use /register <fpl_entry_id> in a private chat to link your team.\n"
        "Mention me in the group or chat privately for FPL insights."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Available commands:\n"
        "/standings [overall|gameweek|monthly]\n"
        "/profile [player name]\n"
        "/winnings [player name]\n"
        "/register <fpl_entry_id>\n"
        "You can also ask me natural-language questions like 'Who should I captain?'"
    )


async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type != "private":
        await update.message.reply_text("Please register in a private chat with me.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /register <fpl_entry_id>")
        return
    try:
        fpl_entry_id = int(args[0])
    except ValueError:
        await update.message.reply_text("fpl_entry_id must be a number.")
        return
    managers = await db.get_managers()
    manager = next((m for m in managers if m["fpl_entry_id"] == fpl_entry_id), None)
    if not manager:
        await update.message.reply_text("That FPL entry is not in the Fantasy Kings league.")
        return
    await db.upsert_telegram_chat({
        "chat_id": chat.id,
        "chat_type": "private",
        "manager_id": manager["id"],
        "fpl_entry_id": fpl_entry_id,
    })
    await update.message.reply_text(f"Registered as {manager['player_name']}.")


async def standings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _upsert_chat(update)
    args = context.args or ["overall"]
    kind = args[0]
    gw = int(args[1]) if len(args) > 1 and kind == "gameweek" else None
    month = args[1] if len(args) > 1 and kind == "monthly" else None
    agent = OllamaAgent()
    response = await agent.chat(f"Show {kind} standings" + (f" for gameweek {gw}" if gw else "") + (f" for {month}" if month else ""))
    await update.message.reply_text(response.reply[:4000])


async def winnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _upsert_chat(update)
    player_name = " ".join(context.args) if context.args else None
    agent = OllamaAgent()
    q = "Show winnings summary" + (f" for {player_name}" if player_name else "")
    response = await agent.chat(q)
    await update.message.reply_text(response.reply[:4000])


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_name = " ".join(context.args) if context.args else None
    chat_record = await _upsert_chat(update)
    if not player_name and chat_record.get("manager_id"):
        # Look up manager name
        managers = await db.get_managers()
        manager = next((m for m in managers if m["id"] == chat_record["manager_id"]), None)
        if manager:
            player_name = manager["player_name"]
    if not player_name:
        await update.message.reply_text("Usage: /profile <player name> or register with /register first.")
        return
    agent = OllamaAgent()
    response = await agent.chat(f"Profile for {player_name}")
    await update.message.reply_text(response.reply[:4000])


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_directed(update, context):
        return
    await _upsert_chat(update)
    text = update.message.text or ""
    username = _bot_username(context)
    clean_text = _strip_mention(text, username)
    agent = OllamaAgent()
    response = await agent.chat(clean_text)
    await update.message.reply_text(response.reply[:4000])
