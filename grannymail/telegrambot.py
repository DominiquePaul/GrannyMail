
from datetime import datetime
import requests
import grannymail.config as cfg
import grannymail.message_utils as msg_utils
import grannymail.db_client as db
from grannymail.pdf_gen import create_letter_pdf_as_bytes
from grannymail.utils import get_message
from grannymail.db_client import User, Message, Draft, Order
from typing import Optional
from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram._callbackquery import CallbackQuery
from telegram.ext import MessageHandler, CallbackContext, filters
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.ext._contexttypes import ContextTypes
from http import HTTPStatus
from grannymail.pingen import Pingen
from contextlib import asynccontextmanager
import logging
logging.basicConfig(level=logging.INFO)


db_client = db.SupabaseClient()
pingen_client = Pingen()

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
    chat_id: int = update.effective_chat.id  # type: ignore
    msg = get_message('help_welcome_message')
    await context.bot.send_message(chat_id=chat_id, text=msg)


async def edit_drafting_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_username: str = (
        update.message.from_user["username"])  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    msg_txt: str = update.message.text  # type: ignore
    user = db_client.get_user(User(telegram_id=telegram_username))

    # If the message is empty we send instructions on how to use the command
    if msg_utils.is_message_empty(msg_txt, "/edit_drafting_prompt"):

        user_error_message = get_message(
            'edit_prompt_msg_empty').format(user.prompt)
        await context.bot.send_message(chat_id=chat_id, text=user_error_message)
        return

    # If the message is not empty, we update the user's prompt with the text
    new_prompt = msg_txt.replace("/edit_prompt", "").strip(" ")
    success_message = get_message('edit_prompt_success').format(new_prompt)
    exit_code, system_error_msg = db_client.update_user(user_data=User(telegram_id=telegram_username),
                                                        user_update=User(prompt=new_prompt))
    if exit_code != 0:
        logging.error(
            "Error from /edit_prompt when trying to update user profile: " + system_error_msg)
    await context.bot.send_message(chat_id=chat_id, text=success_message)


async def show_address_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_username: str = (
        update.message.from_user["username"])  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore

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
    first_name: str = address_book[0].addressee.split(" ")[0]  # type: ignore
    msg = get_message('show_address_book').format(
        formatted_address_book, first_name)
    await context.bot.send_message(chat_id=chat_id, text=msg)


async def add_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_txt: str = update.message.text  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    user_error_message = msg_utils.error_in_address(msg_txt)
    if user_error_message:
        msg = user_error_message
    else:
        address = msg_utils.parse_new_address(msg_txt)
        # add the user_id to the address
        try:
            address.user_id = db_client.get_user(
                db.User(telegram_id=update.message.from_user["username"])).user_id  # type: ignore
            db_client.add_address(address)
            msg = get_message('add_address_success')
        except db.NoEntryFoundError:
            msg = get_message('error_no_user_found')

    await context.bot.send_message(chat_id=chat_id, text=msg)


async def delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_username: str = (
        update.message.from_user["username"])  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    msg_txt: str = update.message.text  # type: ignore
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


async def handle_voice(update: Update, context: CallbackContext):
    telegram_id: str = update.message.from_user["username"]  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    file_id: str = update.message.voice.file_id  # type: ignore
    await context.bot.send_message(chat_id=chat_id, text="A voice memo 😍 Processing... 🤖")
    user = db_client.get_user(User(telegram_id=telegram_id))

    # Download the voice memo from telegram and upload to the database
    file = await context.bot.getFile(file_id)
    voice_bytes = requests.get(file.file_path).content

    # transcribe the voice memo and update message
    logging.info("Transcribing voice memo")
    transcript = msg_utils.transcribe_voice_memo(voice_bytes)

    # Register the message in the database
    message = db_client.register_message(user=user,
                                         sent_by="user",
                                         mime_type="audio/ogg",
                                         msg_text=None,
                                         transcript=transcript)
    db_client.register_voice_memo(voice_bytes, message)
    logging.info("Voice memo w/ success received. Transcript: \n" + transcript)

    # Create a draft and send it to the user
    # Create a pdf
    logging.info("Creating draft text from transcript")
    letter_text = msg_utils.transcript_to_letter_text(transcript, user)
    logging.info("Creating pdf")
    draft_bytes = create_letter_pdf_as_bytes(letter_text)

    # Upload the pdf and register the draft in the database
    db_client.register_draft(
        Draft(user_id=user.user_id, text=letter_text), draft_bytes)

    logging.info("Sending pdf")
    await context.bot.send_document(chat_id, draft_bytes, filename="draft.pdf")


async def handle_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id: str = update.message.from_user["username"]  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    msg_txt: str = msg_utils.strip_command(
        update.message.text, "/send")  # type: ignore
    user = db_client.get_user(User(telegram_id=telegram_id))
    # check whether the user has any addresses to send ot
    if db_client.get_user_addresses(user) == []:
        msg = get_message('send_error_user_has_no_addresses')
        await context.bot.send_message(chat_id=chat_id, text=msg)
        return
    # check whether there is an address mentioned in the message
    if msg == "":
        msg = get_message('send_error_no_address_in_message')
        await context.bot.send_message(chat_id=chat_id, text=msg)
        return
    # check whether there is a previous draft
    draft = db_client.get_last_draft(user)
    if draft is None:
        msg = get_message('send_error_no_draft_found')
        await context.bot.send_message(chat_id=chat_id, text=msg)
        return
    # Is there any letter that has used the last draft? - then append a warning to response
    try:
        db_client.get_order(Order(draft_id=draft.draft_id))
        user_warning = ""
    except db.NoEntryFoundError:
        user_warning = get_message('send_warning_draft_used_before')
    # Find closest matching addrss
    address_book = db_client.get_user_addresses(user)
    address_idx = msg_utils.fetch_closest_address_index(msg_txt, address_book)
    address = address_book[address_idx]

    # Create a letter with the address and the draft text
    logging.info("Creating pdf")
    draft_bytes = create_letter_pdf_as_bytes(
        draft.text, address)  # type: ignore
    db_client.register_draft(
        Draft(user_id=user.user_id, builds_on=draft.draft_id, text=draft.text, address_id=address.address_id), draft_bytes)

    msg = get_message("send_confirmation").format(
        user.first_name) + user_warning
    keyboard = [
        [
            InlineKeyboardButton("Wallah, let's go. ✅",
                                 callback_data={"draft_id": draft.draft_id, "user_confirmed": True}),
            InlineKeyboardButton("Aiiii, no, don't send 🫨",
                                 callback_data={"draft_id": draft.draft_id, "user_confirmed": True}),
        ],
    ]
    await context.bot.send_document(chat_id, draft_bytes, filename="final_letter.pdf")
    await context.bot.send_message(chat_id=chat_id,
                                   reply_markup=InlineKeyboardMarkup(keyboard), text=msg)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query: CallbackQuery = update.callback_query  # type: ignore

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()  # type: ignore

    # Send out letter
    draft_id: str = query.data["draft_id"]  # type: ignore
    user_confirmed: bool = query.data["user_confirmed"]  # type: ignore
    if user_confirmed:
        # Fetch the referenced draft
        draft = db_client.get_draft(Draft(draft_id=draft_id))
        user = db_client.get_user(User(user_id=draft.user_id))
        # download the draft pdf as bytes
        letter_name = f"letter_{user.first_name}_{user.last_name}_{str(datetime.utcnow())}.pdf"
        letter_bytes = db_client.download_draft(draft)
        # create an order and send letter
        order = Order(user_id=user.user_id, draft_id=draft.draft_id,
                      address_id=draft.address_id, blob_path=draft.blob_path)
        db_client.add_order(order)
        pingen_client.upload_and_send_letter(
            letter_bytes, file_name=letter_name)
        await query.edit_message_text(text="Letter sent! 💌")
    else:
        await query.edit_message_text(text="Letter sent! 💌")

# Register our handlers
ptb.add_handler(CommandHandler("help", help))
ptb.add_handler(CommandHandler("add_address", add_address))
ptb.add_handler(CommandHandler("show_address_book", show_address_book))
ptb.add_handler(CommandHandler("delete_address", delete_address))
ptb.add_handler(CommandHandler("edit_prompt", edit_drafting_prompt))
ptb.add_handler(MessageHandler(filters.VOICE, handle_voice))
ptb.add_handler(CallbackQueryHandler(button))
