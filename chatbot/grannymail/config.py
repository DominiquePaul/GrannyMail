import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Telegram bot
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ["BOT_USERNAME"]
TELEGRAM_WEBHOOK_URL = os.environ["TELEGRAM_WEBHOOK_URL"]

# Whatsapp bot
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
WHATSAPP_API_VERSION = os.environ["WHATSAPP_API_VERSION"]
WHATSAPP_PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
WHATSAPP_VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]


# Supabase
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_BUCKET_NAME = os.environ["SUPABASE_BUCKET_NAME"]

# Pingen
PINGEN_ENDPOINT = os.environ["PINGEN_ENDPOINT"]
PINGEN_CLIENT_ID = os.environ["PINGEN_CLIENT_ID"]
PINGEN_CLIENT_SECRET = os.environ["PINGEN_CLIENT_SECRET"]
PINGEN_ORGANISATION_UUID = os.environ["PINGEN_ORGANISATION_UUID"]

# OpenAI
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Google Sheets
MESSAGES_SHEET_NAME = os.environ["MESSAGES_SHEET_COLUMN"]

# Sentry
SENTRY_ENDPOINT = os.getenv("SENTRY_ENDPOINT", None)

STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]
STRIPE_ENDPOINT_SECRET = os.environ["STRIPE_ENDPOINT_SECRET"]

STRIPE_LINK_SINGLE_PAYMENT = "https://buy.stripe.com/test_5kAaIy5FJ9gUes05kl"
STRIPE_LINK_5_CREDITS = "https://buy.stripe.com/test_dR66si4BFeBefw47sv"
STRIPE_LINK_10_CREDITS = "https://buy.stripe.com/test_00gdUK6JN2SwgA83cg"
