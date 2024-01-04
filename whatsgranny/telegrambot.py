import os
import logging
from dotenv import load_dotenv, find_dotenv
from telegram import Update
import telegram as t
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

import utils as u

load_dotenv(find_dotenv())

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = u.get_message('help_welcome_message')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_keyboard = t.KeyboardButton(
        text="send_location", request_location=True)
    contact_keyboard = t.KeyboardButton(
        text="send_contact", request_contact=True)
    custom_keyboard = [[location_keyboard, contact_keyboard]]
    reply_markup = t.ReplyKeyboardMarkup(custom_keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Would you mind sharing your location and contact with me?",
                                   reply_markup=reply_markup)


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.environ['BOT_TOKEN']).build()

    help_handler = CommandHandler('help', help)
    application.add_handler(help_handler)
    setup_handler = CommandHandler('setup', setup)
    application.add_handler(setup_handler)
    location_handler = CommandHandler('location', location)
    application.add_handler(location_handler)

    application.run_polling()
