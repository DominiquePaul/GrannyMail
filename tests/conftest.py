import pytest
from grannymail.db_client import SupabaseClient, User
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


@pytest.fixture
def dbclient():
    # Perform setup for your client object
    client = SupabaseClient()  # Replace with the actual instantiation of your client class
    # You can perform additional setup if needed
    yield client  # This is where the fixture provides the client object to the test
    # Optionally, perform teardown or cleanup after the test is done


@pytest.fixture
def user(dbclient):
    user = User(email="mike@mockowitz.com", first_name="Mike",
                last_name="Mockwitz", telegram_id="mike_mockowitz")
    # Perform setup for your client object
    dbclient.add_user(user)
    user = dbclient.get_user(user)
    # You can perform additional setup if needed
    yield user  # This is where the fixture provides the client object to the test
    # Optionally, perform teardown or cleanup after the test is done
    dbclient.delete_user(User(email="mike@mockowitz.com"))
