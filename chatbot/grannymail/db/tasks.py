import time
import grannymail.domain.models as m
from grannymail.logger import logger
from grannymail.services.unit_of_work import AbstractUnitOfWork, SupabaseUnitOfWork
from grannymail.utils.utils import get_message_spreadsheet


def synchronise_sheet_with_db(uow: AbstractUnitOfWork):
    column_names = list(m.SystemMessage.__annotations__.keys())
    with uow:
        items = uow.system_messages.get_all()
        for item in items:
            uow.system_messages.delete(item.message_identifier)

        # get data from google spreadhsheet and filter out columns that are not in the spreadsheet
        system_message_df = get_message_spreadsheet()
        # filter out columns that are not in the spreadsheet
        system_message_df = system_message_df[
            [col for col in column_names if col in system_message_df.columns]
        ]
        # drop any empty rows
        duplicates = system_message_df[
            system_message_df.duplicated(["message_identifier"], keep=False)
        ]
        if duplicates.any().any():
            raise ValueError(
                f"Duplicate Entries based on 'message_identifier': {str(duplicates)}"
            )

        # warn about any NA values
        na_rows = system_message_df[system_message_df.isna().any(axis=1)]
        if not na_rows.empty:
            logger.warning(f"Rows with NA values: {na_rows}")

        # insert all values from system_message_df into table "system_messages"
        time.sleep(1)
        insert_values = system_message_df.to_dict(orient="records")
        for value_set in insert_values:
            uow.system_messages.add(
                m.SystemMessage(
                    message_identifier=value_set["message_identifier"],
                    message_body=value_set["message_body"],
                )
            )


if __name__ == "__main__":
    with SupabaseUnitOfWork() as uow:
        synchronise_sheet_with_db(uow)
