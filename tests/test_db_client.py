import pytest
from dataclasses import asdict
from grannymail.db_client import User, NoEntryFoundError, Address, Draft
from grannymail.utils import get_prompt_from_sheet


class TestUser():
    def test_to_dict(self):
        user = User(
            first_name="test_dom",
            last_name="test_Paul",
            email="test@dom.com",
            telegram_id="dominique_paul"
        )
        expected = {"first_name": "test_dom",
                    "last_name": "test_Paul",
                    "email": "test@dom.com",
                    "telegram_id": "dominique_paul"}
        assert expected == user.to_dict()


def test_add_user(dbclient):
    # Create a new user
    user_to_add = User(
        first_name="Mike",
        last_name="Tyson",
        email="mike@tyson.com",
        telegram_id="mike_tyson"
    )
    dbclient.add_user(user_to_add)
    user_retrieved = dbclient.get_user(User(telegram_id="mike_tyson"))

    # Check that the returned user is of the right type
    assert isinstance(
        user_retrieved, User), f"Wrong class returned. Expected user, got {type(user_retrieved)}"

    # Check that all values are in the database
    user2_dict = {key: value for key, value in asdict(
        user_retrieved).items() if key in user_to_add.to_dict().keys()}
    assert user_to_add.to_dict() == user2_dict

    # Delete user
    dbclient.delete_user(user_to_add)

    with pytest.raises(NoEntryFoundError) as exc_info:
        dbclient.get_user(User(telegram_id="mike_tyson"))


def test_add_adress(dbclient, user):
    address = Address(
        user_id=user.user_id,
        addressee="test_recipient",
        address_line1="test_address_line1",
        address_line2="test_address_line2",
        city="test_city",
        zip="test_postal_code",
        country="test_country"
    )
    resp = dbclient.add_address(address)
    assert isinstance(resp, Address)
    assert resp.user_id == user.user_id
    assert resp.addressee == "test_recipient"
    assert resp.address_line1 == "test_address_line1"

    address_retrieved = dbclient.get_user_addresses(user)
    assert isinstance(address_retrieved, list)
    assert len(address_retrieved) == 1
    reduced_address_received = {
        key: value for key, value in address_retrieved[0].to_dict().items() if key in address.to_dict()}
    assert address.to_dict() == reduced_address_received

    # delete address
    dbclient.delete_address(address_retrieved[0])
    assert dbclient.get_user_addresses(user) == []


def test_delete_obj(dbclient):
    user = User(telegram_id="d0ominique", email="fictive@email.com")
    dbclient.add_user(user)
    user_full = dbclient.get_user(user)

    with pytest.raises(ValueError) as exc_info:
        dbclient._delete_entry(user)

    assert dbclient._delete_entry(user_full) == 1


def test_update_system_messages(dbclient):
    dbclient.update_system_messages()
    results = dbclient.client.table(
        "system_messages").select("*").execute().data
    assert results != []
    # test that the total number of messages is greater than a certain amount
    assert len(results) > 25
    assert "full_message_name" in results[0].keys()
    assert "version_main" in results[0].keys()


def test_get_system_messages_contains_emoji(dbclient):
    command_name = "send-option-cancel_sending"
    res = dbclient.get_system_message(command_name)
    expected = get_prompt_from_sheet(command_name)
    assert res == expected


def test_get_system_message(dbclient):
    # test that certain messages are in he DB
    res = dbclient.get_system_message("help-success")
    assert isinstance(res, str)
    assert len(res) > 10


def test_get_last_draft(dbclient, user, draft):
    # test that certain messages are in the DB
    res = dbclient.get_last_draft(user)
    assert isinstance(res, Draft)
    assert res.text == draft.text
