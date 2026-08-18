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

import io

from PIL import Image, ImageDraw, ImageFont


def _contains_table(text: str) -> bool:
    return bool(re.search(r"\|.+\|", text, re.MULTILINE))


def _render_table_image(text: str) -> io.BytesIO:
    # Simple renderer: split by lines, parse |col1|col2|...|
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    rows = [[cell.strip() for cell in line.split("|") if cell.strip() != ""] for line in lines]
    
    # Basic sizing
    font = ImageFont.load_default()
    cell_padding = 10
    row_height = 30
    col_widths = [max(font.getlength(str(row[i])) for row in rows) + cell_padding * 2 for i in range(len(rows[0]))]
    img_width = sum(col_widths)
    img_height = row_height * len(rows)

    img = Image.new("RGB", (int(img_width) + 20, int(img_height) + 20), "white")
    draw = ImageDraw.Draw(img)
    y = 10
    for row in rows:
        x = 10
        for i, cell in enumerate(row):
            draw.rectangle([x, y, x + col_widths[i], y + row_height], outline="black")
            draw.text((x + cell_padding, y + 8), str(cell), fill="black", font=font)
            x += col_widths[i]
        y += row_height

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def _resolve_registered_player_name(chat_record: dict) -> str | None:
    manager_id = chat_record.get("manager_id")
    if not manager_id:
        return None
    managers = await db.get_managers()
    manager = next((m for m in managers if m["id"] == manager_id), None)
    return manager.get("player_name") if manager else None


async def _send_reply(update: Update, reply: str) -> None:
    if _contains_table(reply):
        photo = _render_table_image(reply)
        await update.message.reply_photo(photo=photo)
    else:
        await update.message.reply_text(reply)


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
    saved = await db.get_telegram_chat(chat.id)
    return saved or record


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
        "/profile [player name] (defaults to you if registered)\n"
        "/winnings [player name] (defaults to you if registered)\n"
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
    chat_record = await _upsert_chat(update)
    args = context.args or ["overall"]
    kind = args[0]
    gw = int(args[1]) if len(args) > 1 and kind == "gameweek" else None
    month = args[1] if len(args) > 1 and kind == "monthly" else None
    agent = OllamaAgent()
    response = await agent.chat(f"Show {kind} standings" + (f" for gameweek {gw}" if gw else "") + (f" for {month}" if month else ""), chat_id=str(chat_record["chat_id"]))
    await _send_reply(update, response.reply[:4000])


async def winnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_record = await _upsert_chat(update)
    player_name = " ".join(context.args) if context.args else None
    if not player_name:
        player_name = await _resolve_registered_player_name(chat_record)
    agent = OllamaAgent()
    q = "Show winnings summary" + (f" for {player_name}" if player_name else "")
    response = await agent.chat(q, chat_id=str(chat_record["chat_id"]))
    await _send_reply(update, response.reply[:4000])


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_record = await _upsert_chat(update)
    player_name = " ".join(context.args) if context.args else None
    if not player_name:
        player_name = await _resolve_registered_player_name(chat_record)
    if not player_name:
        await update.message.reply_text("Usage: /profile <player name> or register with /register first.")
        return
    agent = OllamaAgent()
    response = await agent.chat(f"Profile for {player_name}", chat_id=str(chat_record["chat_id"]))
    await _send_reply(update, response.reply[:4000])


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_directed(update, context):
        return
    chat_record = await _upsert_chat(update)
    text = update.message.text or ""
    username = _bot_username(context)
    clean_text = _strip_mention(text, username)

    manager_name = await _resolve_registered_player_name(chat_record)
    if manager_name:
        clean_text += f"\n\n(You are answering for the registered manager: {manager_name})"

    agent = OllamaAgent()
    response = await agent.chat(clean_text, chat_id=str(chat_record["chat_id"]))
    await _send_reply(update, response.reply[:4000])
