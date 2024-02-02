from grannymail.db.supaclient import SupabaseClient
import os
import sys

# add the 'grannymail' directory to the path
sys.path.append(os.path.join(sys.path[0], "../"))


db_client = SupabaseClient()
db_client.update_system_messages()
