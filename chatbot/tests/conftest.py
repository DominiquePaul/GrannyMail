import typing as t
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from dotenv import find_dotenv, load_dotenv
from httpx import AsyncClient

import grannymail.domain.models as m
from grannymail.entrypoints.api.fastapi import app
from grannymail.integrations.messengers.whatsapp import WebhookRequestData
from grannymail.utils import utils
from grannymail.utils.message_utils import parse_new_address
from tests.fake_repositories import FakeUnitOfWork

load_dotenv(find_dotenv())

#################


@pytest.fixture
def fake_uow():
    yield FakeUnitOfWork()


@pytest.fixture()
def user() -> m.User:
    return m.User(
        user_id=str(uuid4()),
        created_at=utils.get_utc_timestamp(),
        email="mike@mockowitz.com",
        first_name="Mike",
        last_name="Mockwitz",
        telegram_id="mike_mockowitz",
        phone_number="491515222222",
    )


@pytest.fixture()
def wa_message(user) -> t.Generator[m.WhatsappMessage, None, None]:
    yield m.WhatsappMessage(
        message_id=str(uuid4()),
        user_id=user.user_id,
        phone_number="491515222222",
        messaging_platform="WhatsApp",
        sent_by="user",
        message_type="text",
        timestamp=utils.get_utc_timestamp(),
        message_body="/send doris",
        command="send",
        wa_mid="wamid_12345",
        wa_webhook_id="made_up_id_1234",
        wa_phone_number_id="196914110181234",
        wa_profile_name="Mike Mockowitz",
    )


@pytest.fixture()
def tg_message(user) -> t.Generator[m.TelegramMessage, None, None]:
    yield m.TelegramMessage(
        message_id=str(uuid4()),
        user_id=user.user_id,
        phone_number="491515222222",
        sent_by="user",
        message_type="text",
        timestamp=utils.get_utc_timestamp(),
        message_body="/send doris",
        command="send",
        tg_user_id="1234-9876",
        tg_chat_id=1234,
        tg_message_id="6969",
    )


@pytest.fixture
def address(user, address_string_correct) -> t.Generator[m.Address, None, None]:
    address = parse_new_address(
        address_string_correct, created_at=user.created_at, user_id=user.user_id
    )
    address.user_id = user.user_id
    yield address


@pytest.fixture
def draft(user, address) -> t.Generator[m.Draft, None, None]:
    yield m.Draft(
        draft_id=str(uuid4()),
        blob_path="",
        user_id=user.user_id,
        created_at=user.created_at,
        text="Hallo Doris, mir geht es gut!",
        address_id=address.address_id,
        builds_on=None,
    )


@pytest.fixture
def order(user, address, draft, wa_message) -> t.Generator[m.Order, None, None]:
    yield m.Order(
        order_id=str(uuid4()),
        address_id=address.address_id,
        user_id=user.user_id,
        status="payment_pending",
        payment_type="oneoff",
        message_id=wa_message.message_id,
        draft_id=draft.draft_id,
        blob_path="no_real_path",
    )


@pytest.fixture
def address2(user, address_string_correct2) -> t.Generator[m.Address, None, None]:
    yield parse_new_address(
        address_string_correct2, created_at=user.created_at, user_id=user.user_id
    )


@pytest.fixture
def address_string_correct() -> t.Generator[str, None, None]:
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City\nMock Country"


@pytest.fixture
def address_string_correct2() -> t.Generator[str, None, None]:
    yield "Daddy Yankee\n Main Ave. 99\n50987 \nCologne \nGermany"


@pytest.fixture
def address_string_too_short() -> t.Generator[str, None, None]:
    yield "Mama Mockowitz\nMock Street 42\n12345 \nMock City"


#################


def message_id_generator(start=11111):
    current = start
    while True:
        yield current
        current += 1


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


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


################################################################################################
# Telegram
################################################################################################


# @pytest.fixture
# def tg_send_image_compressed():
#     msg = copy.deepcopy(telegram_message_base)
#     msg["message"].update(
#         {
#             "photo": [
#                 {
#                     "file_id": "AgAreplgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3MAAzQE",
#                     "file_unique_id": "AQADh8YxG1yW4VF4",
#                     "file_size": 451,
#                     "width": 90,
#                     "height": 15,
#                 },
#                 {
#                     "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA20AAzQE",
#                     "file_unique_id": "AQADh8YxG1yW4VFy",
#                     "file_size": 3832,
#                     "width": 320,
#                     "height": 54,
#                 },
#                 {
#                     "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3gAAzQE",
#                     "file_unique_id": "AQADh8YxG1yW4VF9",
#                     "file_size": 14634,
#                     "width": 800,
#                     "height": 134,
#                 },
#                 {
#                     "file_id": "AgACAgQAAxkBAAIB02W8A5Hg69A9X76ivSx2HGquyAABlwACh8YxG1yW4VEoUR0cnQoBPgEAAwIAA3kAAzQE",
#                     "file_unique_id": "AQADh8YxG1yW4VF-",
#                     "file_size": 21995,
#                     "width": 1280,
#                     "height": 214,
#                 },
#             ]
#         }
#     )
#     yield msg


# @pytest.fixture
# def tg_send_image_uncompressed():
#     msg = copy.deepcopy(telegram_message_base)
#     msg["message"].update(
#         {
#             "document": {
#                 "file_name": "Screenshot 2024-01-30 at 12.35.27.png",
#                 "mime_type": "image/png",
#                 "thumbnail": {
#                     "file_id": "AAMCBAADGQEAAgHVZbwD6_qokWrBTshQOT_5S1O8QRsAApcVAAJcluFR9GFC-yH4y3IBAAdtAAM0BA",
#                     "file_unique_id": "AQADlxUAAlyW4VFy",
#                     "file_size": 2956,
#                     "width": 320,
#                     "height": 54,
#                 },
#                 "thumb": {
#                     "file_id": "AAMCBAADGQEAAgHVZbwD6_qokWrBTshQOT_5S1O8QRsAApcVAAJcluFR9GFC-yH4y3IBAAdtAAM0BA",
#                     "file_unique_id": "AQADlxUAAlyW4VFy",
#                     "file_size": 2956,
#                     "width": 320,
#                     "height": 54,
#                 },
#                 "file_id": "BQACAgQAAxkBAAIB1WW8A-v6qJFqwU7IUDk_-UtTvEEbAAKXFQACXJbhUfRhQvsh-MtyNAQ",
#                 "file_unique_id": "AgADlxUAAlyW4VE",
#                 "file_size": 75432,
#             }
#         }
#     )
#     return msg


# @pytest.fixture
# def tg_send_pdf():
#     msg = copy.deepcopy(telegram_message_base)
#     msg["message"].update(
#         {
#             "document": {
#                 "file_name": "20-23004496.pdf",
#                 "mime_type": "application/pdf",
#                 "thumbnail": {
#                     "file_id": "AAMCBAADGQEAAgHWZbwEQwg2qZ5e3zTzeTMsMxbV7B8AApgVAAJcluFROd2g3bdazlMBAAdtAAM0BA",
#                     "file_unique_id": "AQADmBUAAlyW4VFy",
#                     "file_size": 9667,
#                     "width": 226,
#                     "height": 320,
#                 },
#                 "thumb": {
#                     "file_id": "AAMCBAADGQEAAgHWZbwEQwg2qZ5e3zTzeTMsMxbV7B8AApgVAAJcluFROd2g3bdazlMBAAdtAAM0BA",
#                     "file_unique_id": "AQADmBUAAlyW4VFy",
#                     "file_size": 9667,
#                     "width": 226,
#                     "height": 320,
#                 },
#                 "file_id": "BQACAgQAAxkBAAIB1mW8BEMINqmeXt8083kzLDMW1ewfAAKYFQACXJbhUTndoN23Ws5TNAQ",
#                 "file_unique_id": "AgADmBUAAlyW4VE",
#                 "file_size": 315565,
#             }
#         }
#     )
#     return msg


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
