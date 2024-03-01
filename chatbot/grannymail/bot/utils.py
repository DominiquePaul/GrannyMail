import typing as t
import grannymail.db.classes as dbc
from grannymail.bot.whatsapp import WhatsappHandler
from grannymail.bot.telegram import TelegramHandler
from grannymail.db.supaclient import SupabaseClient

dbclient = SupabaseClient()


async def send_message(message_body: str, user_id: str, messaging_platform: str):
    handler: t.Union[TelegramHandler, WhatsappHandler]

    user = dbclient.get_user(dbc.User(user_id=user_id))
    message: dict[str, t.Any] = {
        "user_id": user_id,
        "command": "stripe_webhook",
        "draft_referenced": None,
        "phone_number": user.phone_number,
        "response_to": None,
    }
    if messaging_platform == "Telegram":
        last_user_message = dbclient.get_last_user_message(
            user, messaging_platform=messaging_platform
        )
        assert isinstance(last_user_message, dbc.TelegramMessage)
        message.update(
            {
                "tg_user_id": user.telegram_id,
                "tg_chat_id": last_user_message.tg_chat_id,
            }
        )
        handler = TelegramHandler()
        handler.message = dbc.TelegramMessage(**message)
    elif messaging_platform == "WhatsApp":
        handler = WhatsappHandler()
        handler.message = dbc.WhatsappMessage(**message)
    else:
        raise ValueError(f"Unknown platform: {messaging_platform}")

    await handler.send_message(message_body)
