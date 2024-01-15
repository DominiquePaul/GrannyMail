import os
import sys
# add the 'grannymail' directory to the path
sys.path.append(os.path.join(sys.path[0], '../'))

from grannymail.db_client import SupabaseClient

db_client = SupabaseClient()
db_client.update_system_messages()
