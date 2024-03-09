import datetime
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response, APIRouter
from telegram import Update
from telegram.ext._contexttypes import ContextTypes
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    JobQueue,
    MessageHandler,
    filters,
)

import grannymail.config as cfg
from grannymail.logger import logger
import grannymail.db.tasks as db_tasks
from grannymail.services.unit_of_work import SupabaseUnitOfWork
from grannymail.services.message_processing_service import MessageProcessingService

router = APIRouter()

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


@router.post("/")
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
    with SupabaseUnitOfWork() as uow:
        db_tasks.synchronise_sheet_with_db(uow)


async def handle_voice_text_or_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    with SupabaseUnitOfWork() as uow:
        await MessageProcessingService().receive_and_process_message(
            uow, update=update, context=context
        )
        logger.info("Successfully handled query")


# Register our handlers
ptb.add_handler(
    MessageHandler(filters.TEXT | filters.VOICE, handle_voice_text_or_callback)
)
ptb.add_handler(CallbackQueryHandler(handle_voice_text_or_callback))
job_queue.run_once(job_update_system_messages, 0)
job_queue.run_daily(
    job_update_system_messages,
    days=(0, 1, 2, 3, 4, 5, 6),
    time=datetime.time(hour=6, minute=00, second=00),
)
