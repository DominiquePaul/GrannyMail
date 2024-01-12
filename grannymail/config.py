import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Server setup
WEBHOOK_URL = os.environ['WEBHOOK_URL']

# Telegram bot
BOT_TOKEN = os.environ['BOT_TOKEN']
BOT_USERNAME = os.environ['BOT_USERNAME']

# Supabase
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
SUPABASE_BUCKET_NAME = os.environ['SUPABASE_BUCKET_NAME']

# Pingen
PINGEN_ENDPOINT = os.environ["PINGEN_ENDPOINT"]
PINGEN_CLIENT_ID = os.environ["PINGEN_CLIENT_ID"]
PINGEN_CLIENT_SECRET = os.environ["PINGEN_CLIENT_SECRET"]
PINGEN_ORGANISATION_UUID = os.environ["PINGEN_ORGANISATION_UUID"]

# OpenAI
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Sentry
SENTRY_ENDPOINT = os.getenv("SENTRY_ENDPOINT", None)
