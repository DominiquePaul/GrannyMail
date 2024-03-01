from dataclasses import asdict

import pytest

from grannymail.db.classes import Address, Draft, User
from grannymail.db.supaclient import NoEntryFoundError
from grannymail.utils.utils import get_prompt_from_sheet


class TestUser:
    def test_to_dict(self):
        user = User(
            first_name="test_dom",
            last_name="test_Paul",
            email="test@dom.com",
            telegram_id="dominique_paul",
        )
        expected = {
            "first_name": "test_dom",
            "last_name": "test_Paul",
            "email": "test@dom.com",
            "telegram_id": "dominique_paul",
            "num_letter_credits": 0,
        }
        assert expected == user.to_dict()


def test_add_user(dbclient):
    user_details = {
        "first_name": "Mike",
        "last_name": "Tyson",
        "email": "mike@tyson.com",
        "telegram_id": "mike_tyson",
    }
    # Create and add a new user
    user_to_add = User(**user_details)  # type: ignore
    dbclient.add_user(user_to_add)

    # Retrieve the added user
    user_retrieved = dbclient.get_user(User(telegram_id="mike_tyson"))
    assert isinstance(
        user_retrieved, User
    ), f"Expected User instance, got {type(user_retrieved)}"

    # Validate retrieved user details
    retrieved_user_details = asdict(user_retrieved)
    for key in user_details:
        assert user_details[key] == retrieved_user_details[key], f"Mismatch in {key}"

    # Delete and verify deletion of the user
    dbclient.delete_user(user_to_add)
    with pytest.raises(NoEntryFoundError):
        dbclient.get_user(User(telegram_id="mike_tyson"))


def test_add_adress(dbclient, user):
    address = Address(
        user_id=user.user_id,
        addressee="test_recipient",
        address_line1="test_address_line1",
        address_line2="test_address_line2",
        city="test_city",
        zip="test_postal_code",
        country="test_country",
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
        key: value
        for key, value in address_retrieved[0].to_dict().items()
        if key in address.to_dict()
    }
    assert address.to_dict() == reduced_address_received

    # delete address
    dbclient.delete_address(address_retrieved[0])
    assert dbclient.get_user_addresses(user) == []


def test_delete_obj(dbclient):
    user = User(telegram_id="fake_dominique", email="fictive@email.com")
    user = dbclient.add_user(user)
    assert dbclient._delete_entry(user)


def test_update_system_messages(dbclient):
    dbclient.update_system_messages()
    results = dbclient.client.table("system_messages").select("*").execute().data
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
