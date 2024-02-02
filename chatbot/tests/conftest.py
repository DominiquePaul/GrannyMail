import pytest
from dotenv import find_dotenv, load_dotenv
from fastapi.testclient import TestClient
from telegram import Update
from httpx import AsyncClient
import pytest_asyncio


from grannymail.db.classes import Draft, User
from grannymail.db.supaclient import SupabaseClient
from grannymail.main import app, ptb
from grannymail.utils.message_utils import parse_new_address
from grannymail.bot.whatsapp import WebhookRequestData

load_dotenv(find_dotenv())


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


async def json_to_update_and_context(data: dict):
    update = Update.de_json(data, ptb.bot)
    context = ptb.context_types.context.from_update(update, ptb)
    await context.refresh_data()
    return update, context


##########
# Telegram


@pytest.fixture
async def tg_send_text():
    data = {
        "update_id": 195209681,
        "message": {
            "message_id": 464,
            "from": {
                "id": 1939727828,
                "is_bot": False,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "language_code": "en",
            },
            "chat": {
                "id": 1939727828,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "type": "private",
            },
            "date": 1706820181,
            "text": "/help",
            "entities": [{"offset": 0, "length": 5, "type": "bot_command"}],
        },
    }
    return await json_to_update_and_context(data)


@pytest.fixture
def tg_send_voice_memo():
    data = {
        "update_id": 195209683,
        "message": {
            "message_id": 466,
            "from": {
                "id": 1939727828,
                "is_bot": False,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "language_code": "en",
            },
            "chat": {
                "id": 1939727828,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "type": "private",
            },
            "date": 1706820434,
            "voice": {
                "duration": 2,
                "mime_type": "audio/ogg",
                "file_id": "AwACAgQAAxkBAAIB0mW8A1JnTa3sQDZq8ZIK0QcHzWJSAAKUFQACXJbhUS0E9P4AAW9CZTQE",
                "file_unique_id": "AgADlBUAAlyW4VE",
                "file_size": 7716,
            },
        },
    }
    yield json_to_update_and_context(data)


@pytest.fixture
def tg_send_image_compressed():
    yield {
        "update_id": 195209684,
        "message": {
            "message_id": 467,
            "from": {
                "id": 1939727828,
                "is_bot": False,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "language_code": "en",
            },
            "chat": {
                "id": 1939727828,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "type": "private",
            },
            "date": 1706820497,
            "photo": [
                {
                    "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3MAAzQE",
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
            ],
        },
    }


@pytest.fixture
def tg_send_image_uncompressed():
    yield {
        "update_id": 195209686,
        "message": {
            "message_id": 469,
            "from": {
                "id": 1939727828,
                "is_bot": False,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "language_code": "en",
            },
            "chat": {
                "id": 1939727828,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "type": "private",
            },
            "date": 1706820587,
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
            },
        },
    }


@pytest.fixture
def tg_send_pdf():
    yield {
        "update_id": 195209687,
        "message": {
            "message_id": 470,
            "from": {
                "id": 1939727828,
                "is_bot": False,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "language_code": "en",
            },
            "chat": {
                "id": 1939727828,
                "first_name": "Dominique",
                "last_name": "Paul",
                "username": "dominique_paul",
                "type": "private",
            },
            "date": 1706820676,
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
            },
        },
    }


################################################################################################
# Whatsapp
################################################################################################


@pytest.fixture
def wa_text() -> WebhookRequestData:
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
                                    "profile": {"name": "Dominique Paul"},
                                    "wa_id": "4915159922222",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "4915159922222",
                                    "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBMDIwQjk1NzQ1ODgxRUI1Njk1AA==",
                                    "timestamp": "1706312529",
                                    "text": {"body": "Hello, this is the message"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    )


@pytest.fixture
def wa_text_reply():
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
                                    "profile": {"name": "Dominique Paul"},
                                    "wa_id": "4915159922222",
                                }
                            ],
                            "messages": [
                                {
                                    "context": {
                                        "from": "15551291301",
                                        "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBMDIwQjk1NzQ1ODgxRUI1Njk1AA==",
                                    },
                                    "from": "4915159922222",
                                    "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBMjVBMTJGQjcwRjM1NkZCNzQ4AA==",
                                    "timestamp": "1706567189",
                                    "text": {
                                        "body": "Hi, my message references the one above"
                                    },
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    )


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
                                    "profile": {"name": "Dominique Paul"},
                                    "wa_id": "4915159922222",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "4915159922222",
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


@pytest.fixture
def wa_image_message():
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
                                    "profile": {"name": "Dominique Paul"},
                                    "wa_id": "4915159926263",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "4915159922222",
                                    "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBNUIyN0IzRjE5MUIzREM0Qjc3AA==",
                                    "timestamp": "1706312824",
                                    "type": "image",
                                    "image": {
                                        "mime_type": "image/jpeg",
                                        "sha256": "/EEIcuQqsUpBRW+1KQNd4kTtyhuTYFTI5mTdOwER8Tw=",
                                        "id": "897438572169645",
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


################################################################################################


@pytest.fixture
def dbclient():
    # Perform setup for your client object
    client = (
        SupabaseClient()
    )  # Replace with the actual instantiation of your client class
    # You can perform additional setup if needed
    yield client  # This is where the fixture provides the client object to the test


@pytest.fixture
def user(dbclient):
    user = User(
        email="mike@mockowitz.com",
        first_name="Mike",
        last_name="Mockwitz",
        telegram_id="mike_mockowitz",
    )
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
