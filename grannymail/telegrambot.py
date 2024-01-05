import utils as u
import config as cfg
from contextlib import asynccontextmanager
from http import HTTPStatus
from telegram import Update
from telegram.ext import Application, CommandHandler
from telegram.ext._contexttypes import ContextTypes
from fastapi import FastAPI, Request, Response

print(cfg.BOT_TOKEN)

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
    msg = u.get_message('help_welcome_message')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


ptb.add_handler(CommandHandler("help", help))
