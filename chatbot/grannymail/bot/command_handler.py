import typing as t
from grannymail.db import classes as dbc
import grannymail.db.supaclient as supaclient
from grannymail.bot.telegram import TelegramHandler
from grannymail.bot.whatsapp import WhatsappHandler
import grannymail.utils.message_utils as msg_utils
import grannymail.pdf_gen as pdf_gen
import grannymail.pingen as pingen
import grannymail.stripe_payments as stripe_payments

db_client = supaclient.SupabaseClient()


class NoTranscriptFound(Exception):
    def __init__(self, message):
        super().__init__(message)


class Handler:
    handler: t.Union[WhatsappHandler, TelegramHandler]

    def __init__(self, handler_type: str):
        if handler_type == "WhatsApp":
            self.handler = WhatsappHandler()
        elif handler_type == "Telegram":
            self.handler = TelegramHandler()
        else:
            raise ValueError("Handler type not supported")

    async def parse_message(self, update=None, context=None, data=None):
        if update is not None and context is not None and data is None:
            assert isinstance(self.handler, TelegramHandler)
            await self.handler.parse_message(update, context)
        elif update is None and context is None and data is not None:
            assert isinstance(self.handler, WhatsappHandler)
            await self.handler.parse_message(data)
        else:
            raise ValueError(
                "Either both update and context OR request must be provided, but not both sets together."
            )

    async def handle_no_command(self):
        message_body = db_client.get_system_message("no_command-success")
        await self.handler.send_message(message_body)

    async def handle_help(self):
        message_body = db_client.get_system_message("help-success")
        await self.handler.send_message(message_body)

    async def handle_report_bug(self):
        # check that message is not empty
        if self.handler.message.safe_message_body == "":
            message_body = db_client.get_system_message("report_bug-error-msg_empty")
        else:
            message_body = db_client.get_system_message("report_bug-success")
        await self.handler.send_message(message_body)

    async def handle_edit_prompt(self):
        if self.handler.message.safe_message_body == "":
            response_msg = db_client.get_system_message("edit_prompt-error-msg_empty")
        else:
            new_prompt = self.handler.message.safe_message_body
            user = db_client.get_user(dbc.User(self.handler.message.safe_user_id))
            db_client.update_user(
                user_data=user, user_update=dbc.User(prompt=new_prompt)
            )
            response_msg = db_client.get_system_message("edit_prompt-success").format(
                new_prompt
            )
        await self.handler.send_message(response_msg)

    async def handle_voice(self):
        # Check memo's duration
        if self.handler.message.memo_duration < 5:  # type: ignore
            await self.handler.send_message(
                db_client.get_system_message("voice-warning-duration")
            )

        user = db_client.get_user(dbc.User(self.handler.message.safe_user_id))
        if self.handler.message.transcript is None:
            raise NoTranscriptFound("Transcript is None")

        try:
            letter_text = await msg_utils.transcript_to_letter_text(
                self.handler.message.transcript, user
            )  # type: ignore
        except msg_utils.CharactersNotSupported as e:
            # send a message back to the user
            await self.handler.send_message(
                db_client.get_system_message("voice-error-characters_not_supported")
            )
            return None
        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(letter_text)

        draft_info = db_client.register_draft(
            dbc.Draft(user_id=self.handler.message.safe_user_id, text=letter_text),
            draft_bytes,
        )

        await self.handler.send_document(
            draft_bytes, filename="draft.pdf", mime_type="application/pdf"
        )
        await self.handler.send_message(db_client.get_system_message("voice-success"))

    async def handle_edit(self):
        # fetch the last draft that we're editing
        user = db_client.get_user(dbc.User(self.handler.message.safe_user_id))
        old_draft: dbc.Draft = db_client.get_last_draft(user)  # type: ignore

        if old_draft is None:
            # notify the user that no draft was found
            await self.handler.send_message(
                db_client.get_system_message("edit-error-no_draft_found")
            )
            return None

        # send a confirmation that we're flipping the edits
        await self.handler.send_message(db_client.get_system_message("edit-confirm"))
        old_content: str = old_draft.text  # type: ignore

        # create a new letter text and turn it into a pdf
        new_letter_content = await msg_utils.implement_letter_edits(
            old_content, edit_instructions=self.handler.message.safe_message_body
        )
        new_draft_bytes = pdf_gen.create_letter_pdf_as_bytes(new_letter_content)

        # register new draft
        new_draft = dbc.Draft(
            user_id=user.user_id,
            blob_path=old_draft.blob_path,
            text=new_letter_content,
            builds_on=old_draft.draft_id,
        )
        db_client.register_draft(new_draft, new_draft_bytes)

        # send new draft to user
        await self.handler.send_document(
            new_draft_bytes, filename="draft_updated.pdf", mime_type="application/pdf"
        )
        await self.handler.send_message(
            message_body=db_client.get_system_message("edit-success")
        )

    async def handle_show_address_book(self):
        # Get the user's address book
        user = dbc.User(self.handler.message.safe_user_id)
        address_book = db_client.get_user_addresses(user)

        if len(address_book) == 0:
            error_message = db_client.get_system_message(
                "show_address_book-error-user_has_no_addresses"
            )
            await self.handler.send_message(error_message)
        else:
            # Format and send the address book
            formatted_address_book = msg_utils.format_address_book(address_book)
            addressee: str = address_book[0].addressee  # type: ignore
            first_name: str = addressee.split(" ")[0]
            success_message = db_client.get_system_message(
                "show_address_book-success"
            ).format(formatted_address_book, first_name)
            await self.handler.send_message(success_message)

    async def handle_add_address(self) -> None | dbc.Message:
        user_error_message = msg_utils.error_in_address(
            self.handler.message.safe_message_body
        )
        if user_error_message:
            error_msg = user_error_message
            await self.handler.send_message(error_msg)
            return None

        # Parse the message and add the address to the database
        # we only need this to show the user the formatted address to confirm
        address = msg_utils.parse_new_address(self.handler.message.safe_message_body)

        address_confirmation_format = msg_utils.format_address_for_confirmation(address)
        confirmation_message = db_client.get_system_message(
            "add_address-success"
        ).format(address_confirmation_format)

        option_confirm = db_client.get_system_message("add_address-option-confirm")
        option_cancel = db_client.get_system_message("add_address-option-cancel")
        return await self.handler.send_message_confirmation_request(
            main_msg=confirmation_message,
            cancel_msg=option_cancel,
            confirm_msg=option_confirm,
        )

    async def handle_add_address_callback(self):
        if self.handler.message.action_confirmed:
            # fetch the reply to the original message that contained the address
            response_to_original_message = db_client.get_message(
                dbc.Message(message_id=self.handler.message.response_to)
            )
            # fetch the original message with the address
            original_message = db_client.get_message(
                dbc.Message(message_id=response_to_original_message.response_to)
            )
            assert (
                original_message is not None
            ), "Original message retrieved in address callback is None"
            # parse the address from the original message and add it to DB
            address: dbc.Address = msg_utils.parse_new_address(
                original_message.safe_message_body
            )
            address.user_id = self.handler.message.user_id
            db_client.add_address(address)
            response_msg = db_client.get_system_message("add_address_callback-confirm")
        else:
            response_msg = db_client.get_system_message("add_address_callback-cancel")
        await self.handler.edit_or_send_message(response_msg)

        if self.handler.message.action_confirmed:
            address_book = db_client.get_user_addresses(
                user=dbc.User(user_id=self.handler.message.user_id)
            )
            formatted_address_book = msg_utils.format_address_book(address_book)
            follow_up_address_book_msg = db_client.get_system_message(
                "add_address_callback-success-follow_up"
            ).format(formatted_address_book)
            await self.handler.send_message(follow_up_address_book_msg)

    async def handle_delete_address(self):
        # check msg not empty
        if self.handler.message.safe_message_body == "":
            await self.handler.send_message(
                db_client.get_system_message("delete_address-error-msg_empty")
            )
            return None
        user = dbc.User(self.handler.message.safe_user_id)

        # We first try to convert the message to an integer. If this fails, we try to find the closest match via fuzzy search
        address_book = db_client.get_user_addresses(
            dbc.User(self.handler.message.safe_user_id)
        )
        try:
            reference_idx = int(self.handler.message.safe_message_body)
            # logger.info(
            #     f"Identified message as int and using index {reference_idx} to delete address"
            # )
        except ValueError:
            reference_idx = (
                msg_utils.fetch_closest_address_index(
                    self.handler.message.safe_message_body, address_book
                )
                + 1
            )
            # logger.info(
            #     f"Could not convert message {user_msg} to int. Used fuzzy search and identified address num. {reference_idx} for deletion"
            # )
        if not 0 < reference_idx <= len(address_book):
            await self.handler.send_message(
                db_client.get_system_message("delete_address-error-invalid_idx")
            )
            return None
        address_to_delete = address_book[reference_idx - 1]
        db_client.delete_address(address_to_delete)

        # Let the user know that the address was deleted
        await self.handler.send_message(
            db_client.get_system_message("delete_address-success")
        )

        # Show the updated address book to the user
        unformatted_address_book = db_client.get_user_addresses(user)
        formatted_address_book = msg_utils.format_address_book(unformatted_address_book)
        message_new_adressbook = db_client.get_system_message(
            "delete_address-success-follow_up"
        ).format(formatted_address_book)
        await self.handler.send_message(message_new_adressbook)

    async def handle_send(self) -> None | dbc.Message:
        """Hierarch of checks:
        1. Is there a message body? (required to identify message)
        2. Does the user have a previous draft?
        3. Does the user have any addresses saved?
        """
        user = dbc.User(self.handler.message.safe_user_id)

        # 1. Is message empty?
        if self.handler.message.safe_message_body == "":
            await self.handler.send_message(
                db_client.get_system_message("send-error-msg_empty")
            )
            return None

        # 2. Is there a previous draft?
        last_draft: dbc.Draft = db_client.get_last_draft(user)  # type: ignore
        if last_draft is None:
            await self.handler.send_message(
                db_client.get_system_message("send-error-no_draft")
            )
            return None

        # 3. Does the user have any addresses saved?
        address_book = db_client.get_user_addresses(user)
        if address_book == []:
            await self.handler.send_message(
                db_client.get_system_message("send-error-user_has_no_addresses")
            )
            return None

        user_warning = ""
        # Commented out because this won't work. New send commands will trigger a new
        # try:
        #     db_client.get_order(dbc.Order(draft_id=draft.draft_id))
        #     user_warning = ""
        # except db.NoEntryFoundError:
        #     user_warning = option_confirm = db_client.get_system_message("send-warning-draft_used_before"))

        # Find closest matching address
        address_idx = msg_utils.fetch_closest_address_index(
            self.handler.message.safe_message_body, address_book
        )
        if address_idx == -1:
            formatted_address_book = msg_utils.format_address_book(address_book)
            await self.handler.send_message(
                db_client.get_system_message("send-error-no_good_address_match").format(
                    formatted_address_book
                )
            )
            return None
        address = address_book[address_idx]

        # Create a letter with the address and the draft text
        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(
            last_draft.text, address  # type: ignore
        )
        draft = db_client.register_draft(
            dbc.Draft(
                user_id=user.user_id,
                builds_on=last_draft.draft_id,
                text=last_draft.text,
                address_id=address.address_id,
            ),
            draft_bytes,
        )

        # update the user message in the DB with the draft id so we can retrieve the draft
        # later in the callback response without ambuiguity

        payment_type = "credits" if user.num_letter_credits > 0 else "direct"
        order = db_client.create_order_from_message(
            draft,
            message_id=self.handler.message.message_id,
            status="payment_pending",
            payment_type=payment_type,
        )
        message_updated = self.handler.message.copy()
        message_updated.draft_referenced = draft.draft_id
        message_updated.order_referenced = order.order_id
        db_client.update_message(self.handler.message, message_updated)
        self.handler.message.draft_referenced = draft.draft_id
        self.handler.message.order_referenced = order.order_id

        await self.handler.send_document(
            draft_bytes, filename="final_letter.pdf", mime_type="application/pdf"
        )

        if payment_type == "credits":
            address_formatted = msg_utils.format_address_simple(address)
            user_first_name = (
                " " + user.first_name if user.first_name is not None else ""
            )
            msg = (
                db_client.get_system_message("send-success-credits").format(
                    user.num_letter_credits, user_first_name, address_formatted
                )
                + user_warning
            )
            option_confirm = db_client.get_system_message("send-option-confirm_sending")
            option_cancel = db_client.get_system_message("send-option-cancel_sending")
            return await self.handler.send_message_confirmation_request(
                main_msg=msg, cancel_msg=option_cancel, confirm_msg=option_confirm
            )
        elif payment_type == "direct":
            assert order.order_id is not None
            stripe_link_single_credit = stripe_payments.get_formated_stripe_link(
                num_credits=1, client_reference_id=order.order_id, one_off=True
            )
            msg = (
                db_client.get_system_message("send-success-one_off").format(
                    stripe_link_single_credit
                )
                + user_warning
            )
            return await self.handler.send_message(msg)
        else:
            raise ValueError(f"Payment type {payment_type} not recognized")

    async def handle_send_callback(self):
        if self.handler.message.action_confirmed:
            # fetch the reply to the original message that contained the address
            original_message = db_client.get_message(
                dbc.Message(message_id=self.handler.message.response_to)
            )
            assert original_message.order_referenced is not None
            pingen.dispatch_order(order_id=original_message.order_referenced)
            response_msg = db_client.get_system_message("send_callback-confirm")

        else:
            response_msg = db_client.get_system_message("send_callback-cancel")
        await self.handler.edit_or_send_message(response_msg)

    async def handle_commmand_not_recognised(self):
        message_body = db_client.get_system_message("commmand_not_recognised-success")
        await self.handler.send_message(message_body)
