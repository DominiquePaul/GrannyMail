import grannymail.db.supaclient as supaclient
from grannymail.bot.telegram import TelegramHandler
from grannymail.bot.whatsapp import WhatsappHandler

dbclient = supaclient.SupabaseClient()


class Handler:
    def __init__(self, update=None, context=None, data=None):
        if update is not None and context is not None and data is None:
            self.handler = TelegramHandler(update, context)
        elif update is None and context is None and data is not None:
            self.handler = WhatsappHandler(data)
        else:
            raise ValueError(
                "Either both update and context OR request must be provided, but not both sets together."
            )

    async def parse_message(self):
        await self.handler.parse_message()

    async def handle_help(self):
        message_body = dbclient.get_system_message("help-success")
        await self.handler.send_message(message_body)
