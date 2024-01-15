from dotenv import load_dotenv
from grannymail.db_client import SupabaseClient

load_dotenv()

db_client = SupabaseClient()
db_client.update_system_messages()
