import grannymail.config as cfg
from typing import Optional
from grannymail.utils import get_message
import grannymail.message_utils as msg_utils
import grannymail.db_client as db
from fastapi import FastAPI, Request, Response
from telegram.ext._contexttypes import ContextTypes
from telegram.ext import Application, CommandHandler
from telegram import Update
from http import HTTPStatus
from contextlib import asynccontextmanager
import logging
logging.basicConfig(level=logging.INFO)


db_client = db.SupabaseClient()

# Initialize python telegram bot
ptb = (
    Application.builder()
    .updater(None)
    .token(cfg.BOT_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.setWebhook(cfg.WEBHOOK_URL)
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

# Initialize FastAPI app (similar to Flask)
app = FastAPI(lifespan=lifespan)


@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_message('help_welcome_message')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def show_address_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_username = update.message.from_user["username"]
    chat_id = update.effective_chat.id

    # Try to retrieve the user from the database -  Is the user registered?
    try:
        user = db_client.get_user(db.User(telegram_id=telegram_username))
    except db.NoEntryFoundError:
        error_message = get_message('error_telegram_user_not_found')
        await context.bot.send_message(chat_id=chat_id, text=error_message)
        return

    # Get the user's address book
    address_book = db_client.get_user_addresses(user)
    if not address_book:
        error_message = get_message('show_address_book_no_addresses')
        await context.bot.send_message(chat_id=chat_id, text=error_message)
        return

    # Format and send the address book
    formatted_address_book = msg_utils.format_address_book(address_book)
    first_name = address_book[0].addressee.split(" ")[0]
    msg = get_message('show_address_book').format(
        formatted_address_book, first_name)
    await context.bot.send_message(chat_id=chat_id, text=msg)


async def add_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_txt: Optional[str] = update.message.text
    if msg_txt is None:
        raise TypeError('Message text is None')
    user_error_message = msg_utils.error_in_address(msg_txt)
    if user_error_message:
        msg = user_error_message
    else:
        address = msg_utils.parse_new_address(msg_txt)
        # add the user_id to the address
        try:
            address.user_id = db_client.get_user(
                db.User(telegram_id=update.message.from_user["username"])).user_id
            db_client.add_address(address)
            msg = get_message('add_address_success')
        except db.NoEntryFoundError:
            msg = get_message('error_no_user_found')

    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_username = update.message.from_user["username"]
    chat_id = update.effective_chat.id
    msg_txt: Optional[str] = update.message.text
    logging.info(f"Received message {msg_txt} from {telegram_username}")

    # Try to retrieve the user from the database -  Is the user registered?
    try:
        user = db_client.get_user(db.User(telegram_id=telegram_username))
    except db.NoEntryFoundError:
        error_message = get_message('error_telegram_user_not_found')
        await context.bot.send_message(chat_id=chat_id, text=error_message)
        return

    if msg_utils.is_message_empty(msg_txt):
        error_message = get_message('delete_address_msg_empty')
    msg_txt = msg_txt.replace("/delete_address", "").strip(" ").strip(")")
    # We first try to convert the message to an integer. If this fails, we try to find the closest match via fuzzy search
    address_book = db_client.get_user_addresses(user)
    try:
        reference_idx = int(msg_txt)
        logging.info(
            f"Identified message as int and using index {reference_idx} to delete address")
    except ValueError:
        reference_idx = msg_utils.fetch_closest_address_index(
            msg_txt, address_book)
        logging.info(
            f"Could not convert message {msg_txt} to int. Used fuzzy search to identify index {reference_idx} for deletion")
    if not 0 < reference_idx <= len(address_book):
        error_message = get_message('delete_address_invalid_idx')
        await context.bot.send_message(chat_id=chat_id, text=error_message)
        return
    address_to_delete = address_book[reference_idx-1]
    db_client.delete_address(address_to_delete)
    response_message = get_message('delete_address_success')
    await context.bot.send_message(chat_id=chat_id, text=response_message)


#
ptb.add_handler(CommandHandler("help", help))
ptb.add_handler(CommandHandler("add_address", add_address))
ptb.add_handler(CommandHandler("show_address_book", show_address_book))
ptb.add_handler(CommandHandler("delete_address", delete_address))
