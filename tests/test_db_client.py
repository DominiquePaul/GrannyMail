import os
import pytest
from dataclasses import asdict
from grannymail.db_client import SupabaseClient, User, NoEntryFoundError, Address
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
print(os.environ["SUPABASE_URL"])


@pytest.fixture
def client():
    # Perform setup for your client object
    client = SupabaseClient()  # Replace with the actual instantiation of your client class
    # You can perform additional setup if needed
    yield client  # This is where the fixture provides the client object to the test
    # Optionally, perform teardown or cleanup after the test is done


@pytest.fixture
def client_and_user():
    # Perform setup for your client object
    client = SupabaseClient()  # Replace with the actual instantiation of your client class
    user = User(email="test@test.com")
    client.add_user(user)
    user = client.get_user(user)
    # You can perform additional setup if needed
    yield client, user  # This is where the fixture provides the client object to the test
    # Optionally, perform teardown or cleanup after the test is done
    client.delete_user(User(email="test@test.com"))


class TestUser():
    def test_to_dict(self):
        user = User(
            first_name="test_dom",
            last_name="test_Paul",
            email="Dominique")
        expected = {"first_name": "test_dom",
                    "last_name": "test_Paul",
                    "email": "Dominique"}
        assert expected == user.to_dict()


def test_add_user(client):
    # Create a new user
    user_to_add = User(
        first_name="test_dom",
        last_name="test_Paul",
        email="test@dom.com",
        telegram_id="dominique_paul"
    )
    client.add_user(user_to_add)
    user_retrieved = client.get_user(User(telegram_id="dominique_paul"))

    # Check that the returned user is of the right type
    assert isinstance(
        user_retrieved, User), f"Wrong class returned. Expected user, got {type(user)}"

    # Check that all values are in the database
    user2_dict = {key: value for key, value in asdict(
        user_retrieved).items() if key in user_to_add.to_dict().keys()}
    assert user_to_add.to_dict() == user2_dict

    # Delete user
    client.delete_user(user_to_add)

    with pytest.raises(NoEntryFoundError) as exc_info:
        client.get_user(User(telegram_id="dominique_paul"))


def test_add_adress(client_and_user):
    client, user = client_and_user
    address = Address(
        user_id=user.user_id,
        addressee="test_recipient",
        address_line1="test_address_line1",
        address_line2="test_address_line2",
        city="test_city",
        zip="test_postal_code",
        country="test_country"
    )
    r, _ = client.add_address(address)
    assert r == 0

    address_retrieved = client.get_user_addresses(user)
    assert isinstance(address_retrieved, list)
    reduced_address_received = {
        key: value for key, value in address_retrieved[0].to_dict().items() if key in address.to_dict()}
    assert address.to_dict() == reduced_address_received

    client.delete_address(address_retrieved[0])
    with pytest.raises(NoEntryFoundError) as exc_info:
        client.get_user_addresses(user)
