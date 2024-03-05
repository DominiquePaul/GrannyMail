import grannymail.db.tasks as db_tasks
import grannymail.db.repositories as repos


def test_synchronise_sheet_with_db():
    supaclient = repos.create_supabase_client()
    sm_repo = repos.SystemMessageRepository(supaclient)
    db_tasks.synchronise_sheet_with_db(sm_repo)
