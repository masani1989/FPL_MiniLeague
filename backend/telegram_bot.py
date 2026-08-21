"""Telegram bot handlers and wiring."""
import io
import os
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

from PIL import Image, ImageDraw, ImageFont


def _contains_table(text: str) -> bool:
    return bool(re.search(r"\|.+\|", text, re.MULTILINE))


# Common TrueType font paths across macOS / Linux / Windows.
# Pillow's default bitmap font is tiny; a TTF font looks much crisper.
_SANS_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_SANS_BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _load_font(size: int = 14, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _SANS_BOLD_CANDIDATES if bold else _SANS_FONT_CANDIDATES
    return _find_font(candidates, size)


def _parse_markdown_table(text: str) -> list[list[str]]:
    """Return data rows from a |markdown|table| body, dropping separator lines."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.split("|")]
        # Drop the empty leading/trailing cells produced by the outer pipes.
        while cells and cells[0] == "":
            cells.pop(0)
        while cells and cells[-1] == "":
            cells.pop()
        # Skip markdown separator lines like |---|---|.
        if all(cell.strip("-: ") == "" for cell in cells):
            continue
        rows.append(cells)
    return rows


def _render_table_image(text: str) -> io.BytesIO:
    rows = _parse_markdown_table(text)
    if not rows:
        # No table found; return a tiny blank image so callers can still send a photo.
        img = Image.new("RGB", (1, 1), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    header_font = _load_font(size=15, bold=True)
    body_font = _load_font(size=14, bold=False)
    cell_padding_x = 16
    cell_padding_y = 12
    min_row_height = 28

    num_cols = max(len(row) for row in rows)
    # Pad ragged rows so column math stays simple.
    normalized_rows = [row + [""] * (num_cols - len(row)) for row in rows]

    def cell_size(cell: str, col_index: int, is_header: bool) -> tuple[float, float]:
        font = header_font if is_header else body_font
        bbox = font.getbbox(str(cell))
        width = (bbox[2] - bbox[0]) + cell_padding_x * 2
        height = (bbox[3] - bbox[1]) + cell_padding_y * 2
        return float(width), max(float(height), min_row_height)

    col_widths = [0.0] * num_cols
    row_heights = []
    for row_index, row in enumerate(normalized_rows):
        is_header = row_index == 0
        max_height = min_row_height
        for col_index, cell in enumerate(row):
            width, height = cell_size(cell, col_index, is_header)
            col_widths[col_index] = max(col_widths[col_index], width)
            max_height = max(max_height, height)
        row_heights.append(max_height)

    margin = 16
    img_width = int(sum(col_widths)) + margin * 2
    img_height = int(sum(row_heights)) + margin * 2

    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)

    header_bg = "#1F4E78"
    header_text = "white"
    body_text = "#222222"
    grid_color = "#AAAAAA"
    alt_row_bg = "#F7F7F7"

    y = margin
    for row_index, row in enumerate(normalized_rows):
        is_header = row_index == 0
        x = margin
        row_height = row_heights[row_index]
        bg = header_bg if is_header else (alt_row_bg if row_index % 2 == 0 else "white")
        # Fill the row background before drawing borders/text.
        draw.rectangle([x, y, img_width - margin, y + row_height], fill=bg)

        for col_index, cell in enumerate(row):
            width = col_widths[col_index]
            font = header_font if is_header else body_font
            bbox = font.getbbox(str(cell))
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = x + (width - text_width) / 2
            # Vertically center; bbox[1] is the offset from the top of the em-box.
            text_y = y + (row_height - text_height) / 2 - bbox[1]
            draw.text((text_x, text_y), str(cell), fill=header_text if is_header else body_text, font=font)
            x += width

        # Horizontal line below this row.
        draw.line([margin, y + row_height, img_width - margin, y + row_height], fill=grid_color, width=1)
        y += row_height

    # Vertical grid lines.
    x = margin
    for width in col_widths:
        draw.line([x, margin, x, img_height - margin], fill=grid_color, width=1)
        x += width
    # Closing right border.
    draw.line([x, margin, x, img_height - margin], fill=grid_color, width=1)
    # Top border.
    draw.line([margin, margin, img_width - margin, margin], fill=grid_color, width=1)

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
    app.add_handler(CommandHandler("lms", lms_command))
    app.add_handler(CommandHandler("cc", cc_command))
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
        "/lms [gameweek] (Last Man Standing standings or a gameweek's scorecard)\n"
        "/cc [gameweek|group A|B] (Continental Conquest standings, bracket, fixtures)\n"
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


async def lms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /lms           -> current LMS survivor standings
              /lms <gw>     -> that gameweek's LMS scorecard (eliminated + tiebreakers)"""
    chat_record = await _upsert_chat(update)
    args = context.args or []
    if args:
        query = f"Show Last Man Standing gameweek {args[0]} scorecard"
    else:
        query = "Show Last Man Standing standings"
    agent = OllamaAgent()
    response = await agent.chat(query, chat_id=str(chat_record["chat_id"]))
    await _send_reply(update, response.reply[:4000])


async def cc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /cc                -> Continental Conquest overall standings + bracket
              /cc <gw>          -> that gameweek's CC fixtures/matches
              /cc group A|B     -> group standings table"""
    chat_record = await _upsert_chat(update)
    args = context.args or []
    if args and args[0] == "group":
        group = args[1] if len(args) > 1 else ""
        query = f"Show Continental Conquest group {group} standings"
    elif args:
        query = f"Show Continental Conquest gameweek {args[0]} fixtures"
    else:
        query = "Show Continental Conquest standings and bracket"
    agent = OllamaAgent()
    response = await agent.chat(query, chat_id=str(chat_record["chat_id"]))
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
