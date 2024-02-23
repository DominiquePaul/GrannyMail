import datetime
import json
import logging
import sys
from contextlib import asynccontextmanager
from http import HTTPStatus

import sentry_sdk
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram._callbackquery import CallbackQuery
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    JobQueue,
    MessageHandler,
    filters,
)
from telegram.ext._contexttypes import ContextTypes

import grannymail.bot.whatsapp as whatsapp
import grannymail.config as cfg
import grannymail.db.classes as dbc
import grannymail.db.supaclient as supaclient
from grannymail.db.supaclient import NoUserFound
from grannymail.bot.command_handler import Handler
from grannymail.bot.whatsapp import WebhookRequestData
from grannymail.pdf_gen import create_letter_pdf_as_bytes
from grannymail.pingen import Pingen

# import grannymail.bot.whatsapp as whatsapp

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
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s (%(name)s - %(module)s - %(levelname)s): %(message)s"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


db_client = supaclient.SupabaseClient()
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
    await ptb.bot.setWebhook(cfg.TELEGRAM_WEBHOOK_URL)
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()


# Initialize FastAPI app (similar to Flask)
app = FastAPI(lifespan=lifespan)


@app.router.post("/api/telegram")
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


async def handle_no_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_no_command()


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_help()


async def handle_report_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_report_bug()


async def handle_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_edit_prompt()


async def handle_show_address_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_show_address_book()


async def handle_add_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> dbc.Message | None:
    # missing: check that message isnt empty
    handler = Handler(update, context)
    await handler.parse_message()
    return await handler.handle_add_address()


async def handle_delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handler = Handler(update, context)
    await handler.parse_message()
    return await handler.handle_delete_address()


async def handle_voice(update: Update, context: CallbackContext):
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_voice()


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    handler = Handler(update, context)
    await handler.parse_message()
    await handler.handle_edit()


async def handle_send(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> dbc.Message | None:
    handler = Handler(update, context)
    await handler.parse_message()
    return await handler.handle_send()


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    handler = Handler(update, context)
    await handler.parse_message()
    command = handler.handler.message.command
    if command is not None:
        command_method_name = f"handle_{command}"
        command_method = getattr(handler, command_method_name, None)
        if command_method and callable(command_method):
            await command_method()
        else:
            raise ValueError(
                f"Unknown or uncallable command: {handler.handler.message.command}"
            )


# Register our handlers
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_no_command))
ptb.add_handler(CommandHandler("help", handle_help))
ptb.add_handler(CommandHandler("report_bug", handle_report_bug))
ptb.add_handler(CommandHandler("add_address", handle_add_address))
ptb.add_handler(CommandHandler("show_address_book", handle_show_address_book))
ptb.add_handler(CommandHandler("delete_address", handle_delete_address))
ptb.add_handler(CommandHandler("edit_prompt", handle_edit_prompt))
ptb.add_handler(CommandHandler("edit", handle_edit))
ptb.add_handler(CommandHandler("send", handle_send))
ptb.add_handler(MessageHandler(filters.VOICE, handle_voice))
ptb.add_handler(CallbackQueryHandler(callback_handler))
job_queue.run_once(job_update_system_messages, 0)
job_queue.run_daily(
    job_update_system_messages,
    days=(0, 1, 2, 3, 4, 5, 6),
    time=datetime.time(hour=6, minute=00, second=00),
)


####################
# --- Whatsapp --- #
####################


@app.router.get("/api/whatsapp")
async def verify_route(request: Request):
    return whatsapp.fastapi_verify(request)


@app.router.post("/api/whatsapp")
async def webhook_route(data: WebhookRequestData):
    if data.entry[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
        logging.info("Received a WhatsApp status update.")
        return JSONResponse(content="ok", status_code=200)
    else:
        try:
            handler = Handler(data=data)
            await handler.parse_message()

            # Dynamically call the command method based on the command name
            command = handler.handler.message.command
            if command is not None:
                command_method_name = f"handle_{command}"
                command_method = getattr(handler, command_method_name, None)
                if command_method and callable(command_method):
                    await command_method()
                else:
                    raise ValueError(
                        f"Unknown or uncallable command: {handler.handler.message.command}"
                    )
            return JSONResponse(content="ok", status_code=200)
        except NoUserFound as e:
            logging.error(f"No user found: {e}")
        except:
            return JSONResponse(content="Internal Server Error", status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("grannymail.main:app", host="127.0.0.1", port=8000, reload=True)
