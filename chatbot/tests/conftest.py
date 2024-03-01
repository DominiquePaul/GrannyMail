import pytest
import pytest_asyncio
import typing as t
from dotenv import find_dotenv, load_dotenv
from httpx import AsyncClient
import copy
from unittest.mock import AsyncMock
from unittest.mock import MagicMock


from grannymail.bot.whatsapp import WebhookRequestData
import grannymail.db.classes as dbc
from grannymail.db.supaclient import SupabaseClient
from grannymail.main import app
from grannymail.utils.message_utils import parse_new_address
import grannymail.db.classes as dbc

from tests.test_utils import message_id_generator

load_dotenv(find_dotenv())


def create_mock_async_function(monkeypatch, function_path, message_id_gen):
    async def send_message_side_effect(*args, **kwargs):
        chat_id = kwargs.get("chat_id", 1234)
        message_id = next(message_id_gen)
        return MagicMock(chat_id=chat_id, message_id=message_id)

    mock_function = AsyncMock(side_effect=send_message_side_effect)
    monkeypatch.setattr(function_path, mock_function)
    return mock_function


@pytest.fixture
def mock_send_message_tg(monkeypatch):
    message_id_gen = message_id_generator(start=11111)
    return create_mock_async_function(
        monkeypatch, "telegram.ext.ExtBot.sendMessage", message_id_gen
    )


@pytest.fixture
def mock_send_document_tg(monkeypatch):
    message_id_gen = message_id_generator(start=22222)
    return create_mock_async_function(
        monkeypatch, "telegram.ext.ExtBot.sendDocument", message_id_gen
    )


@pytest.fixture
def mock_edit_message_text_tg(monkeypatch):
    message_id_gen = message_id_generator(start=33333)
    return create_mock_async_function(
        monkeypatch,
        "telegram._callbackquery.CallbackQuery.edit_message_text",
        message_id_gen,
    )


# @pytest.fixture
# def mock_send_message_wa(monkeypatch):
#     message_id_gen = message_id_generator(start=11111)
#     return create_mock_async_function(
#         monkeypatch, "telegram.ext.ExtBot.sendMessage", message_id_gen
#     )


# @pytest.fixture
# def mock_send_document_wa(monkeypatch):
#     message_id_gen = message_id_generator(start=22222)
#     return create_mock_async_function(
#         monkeypatch, "telegram.ext.ExtBot.sendDocument", message_id_gen
#     )


# @pytest.fixture
# def mock_edit_message_text_wa(monkeypatch):
#     message_id_gen = message_id_generator(start=33333)
#     return create_mock_async_function(
#         monkeypatch,
#         "telegram._callbackquery.CallbackQuery.edit_message_text",
#         message_id_gen,
#     )


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


##########
# Telegram
telegram_message_base = {
    "update_id": 10011001,
    "message": {
        "message_id": 464,
        "from": {
            "id": 20022002,
            "is_bot": False,
            "first_name": "Mike",
            "last_name": "Mockowitz",
            "username": "mike_mockowitz",
            "language_code": "en",
        },
        "chat": {
            "id": 1234,
            "first_name": "Mike",
            "last_name": "Mockowitz",
            "username": "mike_mockowitz",
            "type": "private",
        },
        "date": 1706820181,
    },
}

telegram_message_example: dict = copy.deepcopy(telegram_message_base)
telegram_message_example["message"].update(
    {"text": "/help", "entities": [{"offset": 0, "length": 5, "type": "bot_command"}]}
)


@pytest.fixture
def tg_send_text():
    return telegram_message_example


@pytest.fixture
def tg_voice_memo():
    msg = copy.deepcopy(telegram_message_base)
    msg["message"].update(
        {
            "voice": {
                "duration": 14.1,
                "mime_type": "audio/ogg",
                "file_id": "AwACAgQAAxkBAAIB0mW8A1JnTa3sQDZq8ZIK0QcHzWJSAAKUFQACXJbhUS0E9P4AAW9CZTQE",
                "file_unique_id": "AgADlBUAAlyW4VE",
                "file_size": 7716,
            },
        }
    )
    return msg


@pytest.fixture
def tg_send_image_compressed():
    msg = copy.deepcopy(telegram_message_base)
    msg["message"].update(
        {
            "photo": [
                {
                    "file_id": "AgAreplgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3MAAzQE",
                    "file_unique_id": "AQADh8YxG1yW4VF4",
                    "file_size": 451,
                    "width": 90,
                    "height": 15,
                },
                {
                    "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA20AAzQE",
                    "file_unique_id": "AQADh8YxG1yW4VFy",
                    "file_size": 3832,
                    "width": 320,
                    "height": 54,
                },
                {
                    "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3gAAzQE",
                    "file_unique_id": "AQADh8YxG1yW4VF9",
                    "file_size": 14634,
                    "width": 800,
                    "height": 134,
                },
                {
                    "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3kAAzQE",
                    "file_unique_id": "AQADh8YxG1yW4VF-",
                    "file_size": 21995,
                    "width": 1280,
                    "height": 214,
                },
            ]
        }
    )
    yield msg


@pytest.fixture
def tg_send_image_uncompressed():
    msg = copy.deepcopy(telegram_message_base)
    msg["message"].update(
        {
            "document": {
                "file_name": "Screenshot 2024-01-30 at 12.35.27.png",
                "mime_type": "image/png",
                "thumbnail": {
                    "file_id": "AAMCBAADGQEAAgHVZbwD6_qokWrBTshQOT_5S1O8QRsAApcVAAJcluFR9GFC-yH4y3IBAAdtAAM0BA",
                    "file_unique_id": "AQADlxUAAlyW4VFy",
                    "file_size": 2956,
                    "width": 320,
                    "height": 54,
                },
                "thumb": {
                    "file_id": "AAMCBAADGQEAAgHVZbwD6_qokWrBTshQOT_5S1O8QRsAApcVAAJcluFR9GFC-yH4y3IBAAdtAAM0BA",
                    "file_unique_id": "AQADlxUAAlyW4VFy",
                    "file_size": 2956,
                    "width": 320,
                    "height": 54,
                },
                "file_id": "BQACAgQAAxkBAAIB1WW8A-v6qJFqwU7IUDk_-UtTvEEbAAKXFQACXJbhUfRhQvsh-MtyNAQ",
                "file_unique_id": "AgADlxUAAlyW4VE",
                "file_size": 75432,
            }
        }
    )
    return msg


@pytest.fixture
def tg_send_pdf():
    msg = copy.deepcopy(telegram_message_base)
    msg["message"].update(
        {
            "document": {
                "file_name": "20-23004496.pdf",
                "mime_type": "application/pdf",
                "thumbnail": {
                    "file_id": "AAMCBAADGQEAAgHWZbwEQwg2qZ5e3zTzeTMsMxbV7B8AApgVAAJcluFROd2g3bdazlMBAAdtAAM0BA",
                    "file_unique_id": "AQADmBUAAlyW4VFy",
                    "file_size": 9667,
                    "width": 226,
                    "height": 320,
                },
                "thumb": {
                    "file_id": "AAMCBAADGQEAAgHWZbwEQwg2qZ5e3zTzeTMsMxbV7B8AApgVAAJcluFROd2g3bdazlMBAAdtAAM0BA",
                    "file_unique_id": "AQADmBUAAlyW4VFy",
                    "file_size": 9667,
                    "width": 226,
                    "height": 320,
                },
                "file_id": "BQACAgQAAxkBAAIB1mW8BEMINqmeXt8083kzLDMW1ewfAAKYFQACXJbhUTndoN23Ws5TNAQ",
                "file_unique_id": "AgADmBUAAlyW4VE",
                "file_size": 315565,
            }
        }
    )
    return msg


################################################################################################
# Whatsapp
################################################################################################


# @pytest.fixture
# def wa_text_reply():
#     return WebhookRequestData(
#         object="whatsapp_business_account",
#         entry=[
#             {
#                 "id": "206144975918077",
#                 "changes": [
#                     {
#                         "value": {
#                             "messaging_product": "whatsapp",
#                             "metadata": {
#                                 "display_phone_number": "15551291301",
#                                 "phone_number_id": "196914110180497",
#                             },
#                             "contacts": [
#                                 {
#                                     "profile": {"name": "Dominique Paul"},
#                                     "wa_id": "491515222222",
#                                 }
#                             ],
#                             "messages": [
#                                 {
#                                     "context": {
#                                         "from": "15551291301",
#                                         "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBMDIwQjk1NzQ1ODgxRUI1Njk1AA==",
#                                     },
#                                     "from": "4915159922222",
#                                     "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBMjVBMTJGQjcwRjM1NkZCNzQ4AA==",
#                                     "timestamp": "1706567189",
#                                     "text": {
#                                         "body": "Hi, my message references the one above"
#                                     },
#                                     "type": "text",
#                                 }
#                             ],
#                         },
#                         "field": "messages",
#                     }
#                 ],
#             }
#         ],
#     )


@pytest.fixture
def wa_voice_memo():
    return WebhookRequestData(
        object="whatsapp_business_account",
        entry=[
            {
                "id": "206144975918077",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551291301",
                                "phone_number_id": "196914110180497",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Mike Mockowitz"},
                                    "wa_id": "491515222222",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "491515222222",
                                    "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBM0M2MDQ3OEI4RDcxMDMwODE0AA==",
                                    "timestamp": "1706312711",
                                    "type": "audio",
                                    "audio": {
                                        "mime_type": "audio/ogg; codecs=opus",
                                        "sha256": "G1Hj0bsE1u0jOrAronuRexvsU5k+gcGncZCKgbHfcr8=",
                                        "id": "1048715742889904",
                                        "voice": True,
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    )


# @pytest.fixture
# def wa_image_message():
#     return WebhookRequestData(
#         object="whatsapp_business_account",
#         entry=[
#             {
#                 "id": "206144975918077",
#                 "changes": [
#                     {
#                         "value": {
#                             "messaging_product": "whatsapp",
#                             "metadata": {
#                                 "display_phone_number": "15551291301",
#                                 "phone_number_id": "196914110180497",
#                             },
#                             "contacts": [
#                                 {
#                                     "profile": {"name": "Dominique Paul"},
#                                     "wa_id": "491515222222",
#                                 }
#                             ],
#                             "messages": [
#                                 {
#                                     "from": "4915159922222",
#                                     "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBNUIyN0IzRjE5MUIzREM0Qjc3AA==",
#                                     "timestamp": "1706312824",
#                                     "type": "image",
#                                     "image": {
#                                         "mime_type": "image/jpeg",
#                                         "sha256": "/EEIcuQqsUpBRW+1KQNd4kTtyhuTYFTI5mTdOwER8Tw=",
#                                         "id": "897438572169645",
#                                     },
#                                 }
#                             ],
#                         },
#                         "field": "messages",
#                     }
#                 ],
#             }
#         ],
#     )


################################################################################################


@pytest.fixture()
def dbclient() -> t.Generator[SupabaseClient, None, None]:
    # Perform setup for your client object
    client = (
        SupabaseClient()
    )  # Replace with the actual instantiation of your client class
    # You can perform additional setup if needed
    yield client  # This is where the fixture provides the client object to the test


@pytest.fixture()
def user(dbclient) -> t.Generator[dbc.User, None, None]:
    user = dbc.User(
        email="mike@mockowitz.com",
        first_name="Mike",
        last_name="Mockwitz",
        telegram_id="mike_mockowitz",
        phone_number="491515222222",
    )
    if dbclient.user_exists(user):
        dbclient.delete_user(user)
    # Perform setup for your client object
    user = dbclient.add_user(user)
    # You can perform additional setup if needed
    yield user  # This is where the fixture provides the client object to the test
    # Optionally, perform teardown or cleanup after the test is done
    dbclient.delete_user(user)


@pytest.fixture
def address(
    dbclient, user, address_string_correct
) -> t.Generator[dbc.Address, None, None]:
    address = parse_new_address(address_string_correct)
    address.user_id = user.user_id
    address = dbclient.add_address(address)
    yield address
    # no reason to delete since user will be deleted and this cascades into address


@pytest.fixture
def draft(dbclient, user, address) -> t.Generator[dbc.Draft, None, None]:
    draft = dbc.Draft(
        user_id=user.user_id,
        text="Hallo Doris, mir geht es gut!",
        address_id=address.address_id,
    )
    draft = dbclient.add_draft(draft)
    yield draft
    # no need to delete, deletion is cascading with user


@pytest.fixture
def address2(
    dbclient, user, address_string_correct2
) -> t.Generator[dbc.Address, None, None]:
    address = parse_new_address(address_string_correct2)
    address.user_id = user.user_id
    address = dbclient.add_address(address)
    yield address


@pytest.fixture
def address_string_correct() -> t.Generator[str, None, None]:
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City\nMock Country"


@pytest.fixture
def address_string_correct2() -> t.Generator[str, None, None]:
    yield "Daddy Yankee\n Main Ave. 99\n50987 \nCologne \nGermany"


@pytest.fixture
def address_string_too_short() -> t.Generator[str, None, None]:
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City"
