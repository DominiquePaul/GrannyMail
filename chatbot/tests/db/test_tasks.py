import grannymail.db.tasks as db_tasks
from grannymail.services.unit_of_work import SupabaseUnitOfWork


def test_synchronise_sheet_with_db():
    uow = SupabaseUnitOfWork()
    db_tasks.synchronise_sheet_with_db(uow)
