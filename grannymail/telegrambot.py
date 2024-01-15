import sys
import datetime
import requests
import grannymail.config as cfg
import grannymail.message_utils as msg_utils
import grannymail.db_client as db
from grannymail.pdf_gen import create_letter_pdf_as_bytes
from grannymail.db_client import User, Draft, Order
import sentry_sdk
from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram._callbackquery import CallbackQuery
from telegram.ext import MessageHandler, CallbackContext, filters
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.ext import JobQueue
from telegram.ext._contexttypes import ContextTypes
from http import HTTPStatus
from grannymail.pingen import Pingen
from contextlib import asynccontextmanager
import logging

# setup sentry
if cfg.SENTRY_ENDPOINT:
    sentry_sdk.init(
        dsn=cfg.SENTRY_ENDPOINT,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

# set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s (%(name)s - %(module)s - %(levelname)s): %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


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
job_queue: JobQueue = ptb.job_queue  # type: ignore


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


async def job_update_system_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Updates the system messages that are stored in the database.

    This function is called once a day and updates the system messages that are stored in the database. This is done
    to allow for easy customisation of the messages without having to redeploy the bot.
    """
    logger.info("Updating system messages")
    db_client.update_system_messages()


async def default_message_handling(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str,
                                   parse_message: bool = True,
                                   check_msg_not_empty: bool = False,
                                   check_has_addresses: bool = False,
                                   check_last_draft_exists: bool = False
                                   ) -> None | tuple[int, str, User]:
    """Runs through some basics checks and returns a tuple of strings that can be used to send a message to the user.

    There are some things like variable extraction and error handling that are common to all commands. This function
    takes care of these

    Args:
        update (Update): telegram object that contains the message
        context (ContextTypes.DEFAULT_TYPE): telegram context
        command: name of the command that was called. Is used to strip it out of the message text and also to search
            for custom error messages that are tailored to that command
        check_not_empty: whether to check whether the message is empty or not (e.g. for /show_address we don't need
            and further text, but for /add_address we do)

    Returns:
        str: telegram username
        int: telegram chat id
        str: message text with the command stripped out
    """
    telegram_id: str = (update.message.from_user["username"])  # type: ignore
    chat_id: int = update.effective_chat.id  # type: ignore
    if parse_message:
        msg_txt: str = msg_utils.strip_command(
            update.message.text, "/" + command)  # type: ignore
    else:
        msg_txt = ""

    # check whether user exists
    try:
        user = db_client.get_user(User(telegram_id=telegram_id))
    except db.NoEntryFoundError:
        user_error_msg = db_client.get_system_message(
            'system-error-telegram_user_not_found')
        await context.bot.send_message(chat_id=chat_id, text=user_error_msg)
        return None

    # log the message receipt
    logger.info(f"/{command} from {telegram_id}")

    # check that the message is not empty
    if check_msg_not_empty:
        if msg_utils.is_message_empty(msg_txt, "/" + command):
            full_msg_name = command + "-error-" + "msg_empty"
            user_error_msg = db_client.get_system_message(full_msg_name)
            await context.bot.send_message(chat_id=chat_id, text=user_error_msg)
            return None

    # check_whether the user has any addresses
    if check_has_addresses:
        if db_client.get_user_addresses(user) == []:
            full_msg_name = command + "-error-" + "user_has_no_addresses"
            user_error_msg = db_client.get_system_message(full_msg_name)
            await context.bot.send_message(chat_id=chat_id, text=user_error_msg)
            return None

    # check whether there is a previous draft
    if check_last_draft_exists:
        draft = db_client.get_last_draft(user)
        if draft is None:
            full_msg_name = command + "-error-" + "msg_empty"
            user_error_msg = db_client.get_system_message(full_msg_name)
            await context.bot.send_message(chat_id=chat_id, text=user_error_msg)
            return None

    return chat_id, msg_txt, user


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="help")
    if values_returned:
        chat_id, user_msg, _ = values_returned
    else:
        return
    await context.bot.send_message(chat_id=chat_id, text=user_msg)


async def handle_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="edit_prompt", check_msg_not_empty=True)
    if values_returned:
        chat_id, user_msg, user = values_returned
    else:
        return

    # If the message is not empty, we update the user's prompt with the text
    new_prompt = user_msg
    success_message = db_client.get_system_message(
        'edit_prompt-success').format(new_prompt)
    exit_code, system_error_msg = db_client.update_user(user_data=user,
                                                        user_update=User(prompt=new_prompt))
    if exit_code != 0:
        logger.error(
            "Error from /edit_prompt when trying to update user profile: " + system_error_msg)
    await context.bot.send_message(chat_id=chat_id, text=success_message)


async def handle_show_address_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="show_address_book", check_has_addresses=True)
    if values_returned:
        chat_id, _, user = values_returned
    else:
        return

    # Get the user's address book
    address_book = db_client.get_user_addresses(user)

    # Format and send the address book
    formatted_address_book = msg_utils.format_address_book(address_book)
    first_name: str = address_book[0].addressee.split(" ")[0]  # type: ignore
    success_message = db_client.get_system_message('show_address_book-success').format(
        formatted_address_book, first_name)
    await context.bot.send_message(chat_id=chat_id, text=success_message)


async def handle_add_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="add_address", check_msg_not_empty=True)
    if values_returned:
        chat_id, user_msg, user = values_returned
    else:
        return
    user_error_message = msg_utils.error_in_address(user_msg)
    if user_error_message:
        response_msg = user_error_message
    else:
        address = msg_utils.parse_new_address(user_msg)
        # add the user_id to the address
        try:
            address.user_id = user.user_id  # type: ignore
            db_client.add_address(address)
            response_msg = db_client.get_system_message('add_address-success')
        except db.NoEntryFoundError:
            response_msg = db_client.get_system_message(
                'add_address-error-no_user_found')

    await context.bot.send_message(chat_id=chat_id, text=response_msg)


async def handle_delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="delete_address", check_msg_not_empty=True)
    if values_returned:
        chat_id, user_msg, user = values_returned
    else:
        return

    user_msg = user_msg.strip(")")
    # We first try to convert the message to an integer. If this fails, we try to find the closest match via fuzzy search
    address_book = db_client.get_user_addresses(user)
    try:
        reference_idx = int(user_msg)
        logger.info(
            f"Identified message as int and using index {reference_idx} to delete address")
    except ValueError:
        reference_idx = msg_utils.fetch_closest_address_index(
            user_msg, address_book)
        logger.info(
            f"Could not convert message {user_msg} to int. Used fuzzy search to identify index {reference_idx} for deletion")
    if not 0 < reference_idx <= len(address_book):
        error_message = db_client.get_system_message(
            'delete_address-error-invalid_idx')
        await context.bot.send_message(chat_id=chat_id, text=error_message)
        return
    address_to_delete = address_book[reference_idx-1]
    db_client.delete_address(address_to_delete)
    response_message = db_client.get_system_message('delete_address-success')
    await context.bot.send_message(chat_id=chat_id, text=response_message)


async def handle_voice(update: Update, context: CallbackContext):
    values_returned = await default_message_handling(update, context, command="voice", parse_message=False)
    if values_returned:
        chat_id, _, user = values_returned
    else:
        return
    # Let the user know that the memo was received as it might take a few seconds until the
    # draft is returned
    response_voice_memo_received = db_client.get_system_message(
        "voice-confirm")
    await context.bot.send_message(chat_id=chat_id, text=response_voice_memo_received)

    # Download the voice memo from telegram and upload to the database
    file = (
        await context.bot.getFile(update.message.voice.file_id))  # type: ignore
    voice_bytes = requests.get(file.file_path).content

    # transcribe the voice memo and update message
    logger.info("Transcribing voice memo")
    transcript = msg_utils.transcribe_voice_memo(voice_bytes)

    # Register the message in the database
    message = db_client.register_message(user=user,
                                         sent_by="user",
                                         mime_type="audio/ogg",
                                         msg_text=None,
                                         transcript=transcript)
    db_client.register_voice_memo(voice_bytes, message)
    logger.info("Voice memo w/ success received. Transcript: \n" + transcript)

    # Create a draft and send it to the user
    # Create a pdf
    logger.info("Creating draft text from transcript")
    letter_text = msg_utils.transcript_to_letter_text(transcript, user)
    logger.info("Creating pdf")
    draft_bytes = create_letter_pdf_as_bytes(letter_text)

    # Upload the pdf and register the draft in the database
    db_client.register_draft(
        Draft(user_id=user.user_id, text=letter_text), draft_bytes)

    logger.info("Sending pdf")
    resp_msg = db_client.get_system_message("voice-success")
    await context.bot.send_document(chat_id, draft_bytes, filename="draft.pdf")
    await context.bot.send_message(chat_id=chat_id, text=resp_msg)


async def handle_edit_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    values_returned = await default_message_handling(update, context, command="edit", check_last_draft_exists=True)
    if values_returned:
        chat_id, msg_user, user = values_returned
    else:
        return
    confirmation_msg = db_client.get_system_message("edit-confirm")
    await context.bot.send_message(chat_id=chat_id, text=confirmation_msg)
    old_draft: Draft = db_client.get_last_draft(user)  # type: ignore
    old_content: str = old_draft.text  # type: ignore
    prompt = db_client.get_system_message("edit-prompt-implement_changes")
    new_letter_content = msg_utils.implement_letter_edits(
        old_content, msg_user, prompt)

    # create new draft pdf and upload file
    new_draft_bytes = create_letter_pdf_as_bytes(new_letter_content)

    # register new draft
    new_draft = Draft(user_id=user.user_id,
                      blob_path=old_draft.blob_path,
                      text=new_letter_content,
                      builds_on=old_draft.draft_id)
    db_client.register_draft(new_draft, new_draft_bytes)

    # send new draft to user
    resp_msg = db_client.get_system_message("edit-success")
    await context.bot.send_document(chat_id=chat_id, document=new_draft_bytes, filename="draft_updated.pdf")
    await context.bot.send_message(chat_id=chat_id, text=resp_msg)


async def handle_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values_returned = await default_message_handling(update, context, command="voice", check_msg_not_empty=True, check_has_addresses=True, check_last_draft_exists=True)
    if values_returned:
        chat_id, user_msg, user = values_returned
    else:
        return
    draft: Draft = db_client.get_last_draft(user)  # type: ignore
    user_warning = ""
    # Commented out because this won't work. New send commands will trigger a new
    # try:
    #     db_client.get_order(Order(draft_id=draft.draft_id))
    #     user_warning = ""
    # except db.NoEntryFoundError:
    #     user_warning = option_confirm = db_client.get_system_message("send-warning-draft_used_before"))

    # Find closest matching addrss
    address_book = db_client.get_user_addresses(user)
    address_idx = msg_utils.fetch_closest_address_index(user_msg, address_book)
    address = address_book[address_idx]

    # Create a letter with the address and the draft text
    logger.info("Creating pdf")
    draft_bytes = create_letter_pdf_as_bytes(
        draft.text, address)  # type: ignore
    db_client.register_draft(
        Draft(user_id=user.user_id, builds_on=draft.draft_id, text=draft.text, address_id=address.address_id), draft_bytes)

    msg = db_client.get_system_message(
        "send-success").format(user.first_name) + user_warning
    option_confirm = db_client.get_system_message(
        "send-option-confirm_sending")
    option_cancel = db_client.get_system_message("send-option-cancel_sending")
    keyboard = [
        [
            InlineKeyboardButton(option_confirm,
                                 callback_data={"draft_id": draft.draft_id, "user_confirmed": True}),
            InlineKeyboardButton(option_cancel,
                                 callback_data={"draft_id": draft.draft_id, "user_confirmed": True}),
        ],
    ]
    await context.bot.send_document(chat_id, draft_bytes, filename="final_letter.pdf")
    await context.bot.send_message(chat_id=chat_id,
                                   reply_markup=InlineKeyboardMarkup(keyboard), text=msg)


async def callback_send_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query: CallbackQuery = update.callback_query  # type: ignore
    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()  # type: ignore
    telegram_id: str = update.message.from_user["username"]  # type: ignore
    # Send out letter
    draft_id: str = query.data["draft_id"]  # type: ignore
    user_confirmed: bool = query.data["user_confirmed"]  # type: ignore
    logging.info(
        f"Final Sending Callback from TID: {telegram_id} with response: {user_confirmed}")
    if user_confirmed:
        # Fetch the referenced draft
        draft = db_client.get_draft(Draft(draft_id=draft_id))
        user = db_client.get_user(User(user_id=draft.user_id))
        # download the draft pdf as bytes
        letter_name = f"letter_{user.first_name}_{user.last_name}_{str(datetime.datetime.utcnow())}.pdf"
        letter_bytes = db_client.download_draft(draft)
        # create an order and send letter
        order = Order(user_id=user.user_id, draft_id=draft.draft_id,
                      address_id=draft.address_id, blob_path=draft.blob_path)
        db_client.add_order(order)
        pingen_client.upload_and_send_letter(
            letter_bytes, file_name=letter_name)
        response_msg = db_client.get_system_message(
            "send_confirmation-confirm")
    else:
        response_msg = db_client.get_system_message(
            "send_confirmation-cancel")
    await query.edit_message_text(text=response_msg)

# Register our handlers
ptb.add_handler(CommandHandler("help", handle_help))
ptb.add_handler(CommandHandler("add_address", handle_add_address))
ptb.add_handler(CommandHandler("show_address_book", handle_show_address_book))
ptb.add_handler(CommandHandler("delete_address", handle_delete_address))
ptb.add_handler(CommandHandler("edit_prompt", handle_edit_prompt))
ptb.add_handler(CommandHandler("edit_draft", handle_edit_draft))
ptb.add_handler(MessageHandler(filters.VOICE, handle_voice))
ptb.add_handler(CallbackQueryHandler(callback_send_confirmation))
job_queue.run_once(job_update_system_messages, 0)
job_queue.run_daily(job_update_system_messages, days=(0, 1, 2, 3, 4, 5, 6),
                    time=datetime.time(hour=6, minute=00, second=00))
