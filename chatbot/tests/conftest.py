import pytest
from grannymail.db_client import SupabaseClient, User, Draft
from grannymail.utils.message_utils import parse_new_address
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


@pytest.fixture
def dbclient():
    # Perform setup for your client object
    client = SupabaseClient()  # Replace with the actual instantiation of your client class
    # You can perform additional setup if needed
    yield client  # This is where the fixture provides the client object to the test


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
    dbclient.delete_user(user)


@pytest.fixture
def draft(dbclient, user):
    draft = Draft(user_id=user.user_id, text="Hallo Doris, mir geht es gut!")
    draft = dbclient.add_draft(draft)
    yield draft
    # no need to delete, deletion is cascading


@pytest.fixture
def address(dbclient, user, address_string_correct):
    address = parse_new_address(address_string_correct)
    address.user_id = user.user_id
    address = dbclient.add_address(address)
    yield address
    # no reason to delete since user will be deleted and this cascades into address


@pytest.fixture
def address_string_correct():
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City\nMock Country"


@pytest.fixture
def address_string_too_short():
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City"
