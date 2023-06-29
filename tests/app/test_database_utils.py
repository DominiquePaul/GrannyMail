from whatsgranny.app.database_utils import Supabase_sql_client

CLIENT = Supabase_sql_client()

class TestSupabaseClient:

    def test_can_add_user(self):
        if len((CLIENT.supabase.table("users").select("*").eq("email", "mm@gmail.com").execute()).data) > 0:
            CLIENT.supabase.table("users").delete().eq("email", "mm@gmail.com").execute()
        r = CLIENT.add_user(first_name="Max", last_name = "Musterman", email= "mm@gmail.com", phone_number= "123456789")

    def test_cant_add_duplicate_user(self):
        # test for duplicate phone number
        code, message = CLIENT.add_user(first_name="Fake Dom", last_name = "Fake Paul", email= "newemail@gmail.com", phone_number= "4915159926162")
        assert code == 1
        # test for duplicate email
        code, message = CLIENT.add_user(first_name="Fake Dom", last_name = "Fake Paul", email= "dominique.c.a.paul@gmail.com", phone_number= "1234567")
        assert code == 2
