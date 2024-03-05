import grannymail.db.classes as dbc
import grannymail.db.repositories as repos
from grannymail.utils.utils import get_message_spreadsheet


def synchronise_sheet_with_db(sm_repo: repos.SystemMessageRepository):
    column_names = list(dbc.SystemMessage.__annotations__.keys())

    items = sm_repo.get_all()
    for item in items:
        sm_repo.delete(item.message_identifier)

    # get data from google spreadhsheet and filter out columns that are not in the spreadsheet
    system_message_df = get_message_spreadsheet()
    system_message_df = system_message_df[
        [col for col in column_names if col in system_message_df.columns]
    ]
    insert_values = system_message_df.to_dict(orient="records")

    # insert all values from system_message_df into table "system_messages"
    for value_set in insert_values:
        sm_repo.add(
            dbc.SystemMessage(
                message_identifier=value_set["message_identifier"],
                message_body=value_set["message_body"],
            )
        )


if __name__ == "__main__":
    supaclient = repos.create_supabase_client()
    sm_repo = repos.SystemMessageRepository(supaclient)
    synchronise_sheet_with_db(sm_repo)
