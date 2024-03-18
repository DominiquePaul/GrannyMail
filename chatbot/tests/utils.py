import copy
import json
import random
import string
import typing as t
from unittest.mock import AsyncMock, MagicMock

from telegram import Update

from grannymail.entrypoints.api.endpoints.telegram import ptb
from grannymail.integrations.messengers.whatsapp import WebhookRequestData


def generate_whatsapp_httpx_response(start_id=1000):
    while True:
        yield {"messages": [{"id": f"wamid_{start_id}"}]}
        start_id += 1


def create_mock_update(data: dict) -> Update:
    """
    Factory function to create a mock Update object from a given data dictionary.
    """
    update = Update.de_json(data, ptb.bot)
    assert update is not None
    return update


# Text updates


def _get_base_tg_message():
    return {
        "update_id": 10011001,
        "message": {
            "message_id": 6969,
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
            "date": 1706312529,
        },
    }


def create_text_message(platform: str, user_msg: str):
    whatsapp_data, update, context = None, None, None
    if platform == "WhatsApp":
        whatsapp_data = _create_whatsapp_text_message(user_msg)
    elif platform == "Telegram":
        update, context = _create_telegram_text_message_objects(user_msg)
    else:
        raise ValueError(f"platform {platform} not found")
    return whatsapp_data, update, context


def _get_base_wa_message(messages):
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
                            "messages": messages,
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    )


def _create_whatsapp_text_message(message_body: str, wamid: str | None = None):
    if wamid is None:
        wamid = "wamid." + "".join(
            random.choices(string.ascii_letters + string.digits, k=50)
        )
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
                                    "from": "4915159922222",
                                    "id": wamid,
                                    "timestamp": "1706312529",
                                    "text": {"body": message_body},
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


def _create_telegram_text_message_objects(text):
    tg_msg = _get_base_tg_message()
    tg_msg["message"].update(
        {"text": text, "entities": [{"offset": 0, "length": 5, "type": "bot_command"}]}
    )

    mock_update = create_mock_update(tg_msg)
    mock_context = AsyncMock()  # Mock the context
    mock_context.bot.send_message = AsyncMock(
        return_value=MagicMock(chat_id=1234, message_id=10001)
    )
    return mock_update, mock_context


# Voice memos


def create_voice_memo_msg(platform):
    whatsapp_data, update, context = None, None, None
    if platform == "WhatsApp":
        whatsapp_data = _create_wa_voice_memo_msg()
    elif platform == "Telegram":
        update, context = _create_tg_voice_memo_msg()
    else:
        raise ValueError(f"platform {platform} not found")
    return whatsapp_data, update, context


def _create_wa_voice_memo_msg():
    return _get_base_wa_message(
        [
            {
                "from": "491515222222",
                "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBM0M2MDQ3OEI4RDcxMDMwODE0AA==",
                "timestamp": "1706312529",
                "type": "audio",
                "audio": {
                    "mime_type": "audio/ogg; codecs=opus",
                    "sha256": "G1Hj0bsE1u0jOrAronuRexvsU5k+gcGncZCKgbHfcr8=",
                    "id": "1048715742889904",
                    "voice": True,
                },
            }
        ]
    )


def _create_tg_voice_memo_msg():
    tg_msg = _get_base_tg_message()
    tg_msg["message"].update(
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
    mock_update = create_mock_update(tg_msg)
    mock_context = AsyncMock()  # Mock the context
    mock_context.bot.send_message = AsyncMock(
        return_value=MagicMock(chat_id=1234, message_id=10001)
    )
    return mock_update, mock_context


# Callbacks


def create_callback_message(
    platform: str,
    reference_message_id: str,
    action_confirmed: t.Literal["true", "false"],
):
    whatsapp_data, update, context = None, None, None
    if platform == "WhatsApp":
        whatsapp_data = create_whatsapp_callback_message(
            reference_message_id, action_confirmed
        )
    elif platform == "Telegram":
        action_confirmed_bool = True if action_confirmed == "true" else False
        update, context = create_telegram_callback_message(
            reference_message_id, action_confirmed_bool
        )
    else:
        raise ValueError("Platform {platform} is not a valid input")
    return whatsapp_data, update, context


def create_whatsapp_callback_message(
    reference_message_id: str, action_confirmed: t.Literal["true", "false"]
):
    title = "✅" if action_confirmed == "true" else "❌"
    return _get_base_wa_message(
        [
            {
                "context": {
                    "from": "491515222222",
                    "id": reference_message_id,
                },
                "from": "4915159926162",
                "id": "wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBQzk0NUREMERBQkVEMDI3MUZBAA==",
                "timestamp": "1706312529",
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {
                        "id": action_confirmed,
                        "title": title,
                    },
                },
            }
        ]
    )


def _get_telegram_callback_request(reference_message_id: str, action_confirmed: bool):
    return {
        "update_id": 195209714,
        "callback_query": {
            "id": "8331067584627650864",
            "from": {
                "id": 1234,
                "is_bot": False,
                "first_name": "Mike",
                "last_name": "Mockowitz",
                "username": "mike_mockowitz",
                "language_code": "en",
            },
            "message": {
                "message_id": 6969,
                "from": {
                    "id": 6905727299,
                    "is_bot": True,
                    "first_name": "GrannyMailDev",
                    "username": "GrannyMailDevBot",
                },
                "chat": {
                    "id": 1234,
                    "first_name": "Mike",
                    "last_name": "Mockowitz",
                    "username": "mike_mockowitz",
                    "type": "private",
                },
                "date": 1707447364,
                "text": "Got it! 📮\n\nIs this correct?\nAddressee: Dominique Paul\nAddress line 1: Marienburgerstraße 49\nPostal Code: 50968  \nCity/Town: Cologne\nCountry: Germany",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "✅",
                                "callback_data": f"{{'mid': '{reference_message_id}', 'conf': true}}",
                            },
                            {
                                "text": "❌",
                                "callback_data": f"{{'mid': '{reference_message_id}', 'conf': false}}",
                            },
                        ]
                    ]
                },
            },
            "chat_instance": "-2035293384663480539",
            "data": json.dumps({"mid": reference_message_id, "conf": action_confirmed}),
        },
    }


def create_telegram_callback_message(reference_mid: str, action_confirmed: bool):
    tg_message = _get_telegram_callback_request(reference_mid, action_confirmed)
    mock_update = create_mock_update(tg_message)
    # mock_update.message.date = ""
    mock_context = AsyncMock()  # Mock the context
    mock_context.bot.send_message = AsyncMock(
        return_value=MagicMock(chat_id=1234, message_id=10002)
    )
    return mock_update, mock_context


# def stripe_webhook_payload(client_reference_id: str) -> dict:
#     return {
#         "api_version": "2023-10-16",
#         "created": 1709244166,
#         "data": {
#             "object": {
#                 "after_expiration": None,
#                 "allow_promotion_codes": False,
#                 "amount_subtotal": 249,
#                 "amount_total": 249,
#                 "automatic_tax": {"enabled": False, "liability": None, "status": None},
#                 "billing_address_collection": "auto",
#                 "cancel_url": "https://stripe.com",
#                 "client_reference_id": client_reference_id,
#                 "client_secret": None,
#                 "consent": None,
#                 "consent_collection": {
#                     "payment_method_reuse_agreement": None,
#                     "promotions": "none",
#                     "terms_of_service": "none",
#                 },
#                 "created": 1709244150,
#                 "currency": "eur",
#                 "currency_conversion": None,
#                 "custom_fields": [],
#                 "custom_text": {
#                     "after_submit": None,
#                     "shipping_address": None,
#                     "submit": None,
#                     "terms_of_service_acceptance": None,
#                 },
#                 "customer": None,
#                 "customer_creation": "if_required",
#                 "customer_details": {
#                     "address": {
#                         "city": None,
#                         "country": "AR",
#                         "line1": None,
#                         "line2": None,
#                         "postal_code": None,
#                         "state": None,
#                     },
#                     "email": "test@test.com",
#                     "name": "test test",
#                     "phone": None,
#                     "tax_exempt": "none",
#                     "tax_ids": [],
#                 },
#                 "customer_email": None,
#                 "expires_at": 1709330549,
#                 "id": "cs_test_a1RjMHtBo1tOaT8fNUZ9OBbJDizbsWZRRimMFHCz7aOPAeuPt1olGjwcdt",
#                 "invoice": None,
#                 "invoice_creation": {
#                     "enabled": False,
#                     "invoice_data": {
#                         "account_tax_ids": None,
#                         "custom_fields": None,
#                         "description": None,
#                         "footer": None,
#                         "issuer": None,
#                         "metadata": {},
#                         "rendering_options": None,
#                     },
#                 },
#                 "livemode": False,
#                 "locale": "auto",
#                 "metadata": {},
#                 "mode": "payment",
#                 "object": "checkout.session",
#                 "payment_intent": "pi_3OpHgeLuDIWxSZxa0kcjZEW0",
#                 "payment_link": "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ",
#                 "payment_method_collection": "if_required",
#                 "payment_method_configuration_details": {
#                     "id": "pmc_1OnfihLuDIWxSZxaTYITyZOM",
#                     "parent": None,
#                 },
#                 "payment_method_options": {},
#                 "payment_method_types": [
#                     "card",
#                     "bancontact",
#                     "eps",
#                     "giropay",
#                     "ideal",
#                     "klarna",
#                     "link",
#                 ],
#                 "payment_status": "paid",
#                 "phone_number_collection": {"enabled": False},
#                 "recovered_from": None,
#                 "setup_intent": None,
#                 "shipping_address_collection": None,
#                 "shipping_cost": None,
#                 "shipping_details": None,
#                 "shipping_options": [],
#                 "status": "complete",
#                 "submit_type": "auto",
#                 "subscription": None,
#                 "success_url": "https://stripe.com",
#                 "total_details": {
#                     "amount_discount": 0,
#                     "amount_shipping": 0,
#                     "amount_tax": 0,
#                 },
#                 "ui_mode": "hosted",
#                 "url": None,
#             }
#         },
#         "type": "checkout.session.completed",
#     }
