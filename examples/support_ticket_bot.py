#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.
"""Example of a simple support ticket bot.

Users can send direct messages to create tickets. Those messages will be
forwarded to a dedicated admin chat where staff can reply via ``/reply``.
Replies are relayed back to the user. Tickets can be closed with ``/close``.
Set ``BOT_TOKEN`` and ``ADMIN_CHAT_ID`` as environment variables before running.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Update

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))


@dataclass
class Ticket:
    """Data stored for each support ticket."""

    id: int
    user_id: int
    username: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_open: bool = True


tickets: dict[int, Ticket] = {}


def next_ticket_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return a new incremental ticket ID."""
    counter = context.application.bot_data.get("ticket_counter", 0) + 1
    context.application.bot_data["ticket_counter"] = counter
    return counter


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user and instruct how to open a ticket."""
    await update.message.reply_text(
        "Hi! \U0001F6CE\ufe0f Send me your question and I'll connect you to our support team."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a ticket from the user's message and forward it."""
    message = update.message
    if not message:
        return
    user = message.from_user
    ticket_id = next_ticket_id(context)
    tickets[ticket_id] = Ticket(ticket_id, user.id, user.username or user.full_name)

    admin_text = (
        f"\U0001F4E7 New ticket #{ticket_id} from {user.mention_html()}:\n"
        f"{message.text_html or ''}"
    )
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="HTML"
    )
    await message.reply_text(
        f"\U0001F39F\ufe0f Your ticket #{ticket_id} has been created. We'll get back to you soon."
    )


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to a ticket from the admin chat."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /reply <ticket_id> <reply>")
        return

    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ticket ID must be a number.")
        return
    if ticket_id not in tickets:
        await update.message.reply_text("Ticket not found.")
        return

    reply_text = " ".join(context.args[1:])
    ticket = tickets[ticket_id]
    await context.bot.send_message(
        chat_id=ticket.user_id,
        text=f"\U0001F4AC Support reply to ticket #{ticket_id}:\n{reply_text}",
    )
    await update.message.reply_text(f"Replied to ticket #{ticket_id}")


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Close a ticket from the admin chat."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /close <ticket_id>")
        return

    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ticket ID must be a number.")
        return

    ticket = tickets.get(ticket_id)
    if not ticket:
        await update.message.reply_text("Ticket not found.")
        return

    ticket.is_open = False
    await context.bot.send_message(
        chat_id=ticket.user_id,
        text=f"\u2705 Your ticket #{ticket_id} has been closed.",
    )
    await update.message.reply_text(f"Closed ticket #{ticket_id}")


def main() -> None:
    """Run the bot."""
    token = os.environ["BOT_TOKEN"]
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reply", reply))
    application.add_handler(CommandHandler("close", close))
    application.add_handler(MessageHandler(filters.TEXT & filters.PRIVATE, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
