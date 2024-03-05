from datetime import datetime
from uuid import uuid4
import typing as t
from grannymail.db import classes as dbc
from grannymail.bot.telegram import TelegramHandler
from grannymail.bot.whatsapp import WhatsappHandler
import grannymail.utils.message_utils as msg_utils
import grannymail.pdf_gen as pdf_gen
import grannymail.pingen as pingen
import grannymail.stripe_payments as stripe_payments
import grannymail.db.repositories as repos
from grannymail.logger import logger

supaclient = repos.create_supabase_client()


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
        sm_repo = repos.SystemMessageRepository(supaclient)
        message_body = sm_repo.get_msg("no_command-success")
        await self.handler.send_message(message_body)

    async def handle_help(self):
        sm_repo = repos.SystemMessageRepository(supaclient)
        message_body = sm_repo.get_msg("help-success")
        await self.handler.send_message(message_body)

    async def handle_report_bug(self):
        # check that message is not empty
        sm_repo = repos.SystemMessageRepository(supaclient)
        msg_id = (
            "report_bug-error-msg_empty"
            if self.handler.message.safe_message_body == ""
            else "report_bug-success"
        )
        message_body = sm_repo.get_msg(msg_id)
        await self.handler.send_message(message_body)

    async def handle_edit_prompt(self):
        user_repo = repos.UserRepository(supaclient)
        sm_repo = repos.SystemMessageRepository(supaclient)

        if self.handler.message.safe_message_body == "":
            message_body = sm_repo.get_msg("edit_prompt-error-msg_empty")
        else:
            new_prompt = self.handler.message.safe_message_body

            user = user_repo.get(self.handler.message.safe_user_id)
            user.prompt = new_prompt
            user_repo.update(user)
            message_body = sm_repo.get_msg("edit_prompt-success").format(new_prompt)
        await self.handler.send_message(message_body)

    async def handle_voice(self):
        # Check memo's duration
        user_repo = repos.UserRepository(supaclient)
        sm_repo = repos.SystemMessageRepository(supaclient)
        draft_repo = repos.DraftRepository(supaclient)
        blob_draft_repo = repos.DraftBlobRepository(supaclient)

        if self.handler.message.memo_duration < 5:  # type: ignore
            message_body = sm_repo.get_msg("voice-warning-duration")
            await self.handler.send_message(message_body)

        user = user_repo.get(self.handler.message.safe_user_id)

        if self.handler.message.transcript is None:
            raise NoTranscriptFound("Transcript is None")
        try:
            letter_text = await msg_utils.transcript_to_letter_text(
                self.handler.message.transcript, user.user_id
            )  # type: ignore
        except msg_utils.CharactersNotSupported as e:
            # send a message back to the user
            error_message = sm_repo.get_msg("voice-error-characters_not_supported")
            await self.handler.send_message(error_message)
            return None
        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(letter_text)

        ##############
        # 1. Upload file to blob storage
        full_path = blob_draft_repo.create_file_path(self.handler.message.safe_user_id)
        blob_draft_repo.upload(draft_bytes, full_path, "application/pdf")

        # 2. Register the draft in the DB
        draft = dbc.Draft(
            draft_id=str(uuid4()),
            user_id=user.user_id,
            created_at=self.handler.message.timestamp,
            text=letter_text,
            blob_path=full_path,
            address_id=None,
            builds_on=None,
        )
        draft = draft_repo.add(draft)
        ####################

        await self.handler.send_document(
            draft_bytes, filename="draft.pdf", mime_type="application/pdf"
        )
        message_body = sm_repo.get_msg("voice-success")
        await self.handler.send_message(message_body)

    async def handle_edit(self):
        # fetch the last draft that we're editing
        user_repo = repos.UserRepository(supaclient)
        sm_repo = repos.SystemMessageRepository(supaclient)
        user = user_repo.get(self.handler.message.safe_user_id)
        draft_repo = repos.DraftRepository(supaclient)
        blob_draft_repo = repos.DraftBlobRepository(supaclient)

        old_draft = draft_repo.get(
            id=None, filters={"user": user.user_id}, order={"created_at": "desc"}
        )

        # If we find no previous draft we respond with an error
        if old_draft is None:
            error_msg = sm_repo.get_msg("edit-error-no_draft_found")
            await self.handler.send_message(error_msg)
            return None

        # Send a message to let user know that command was received and something is happening
        message_body = sm_repo.get_msg("edit-confirm")
        await self.handler.send_message(message_body)
        old_content: str = old_draft.text  # type: ignore

        # Generate the new letter content
        new_letter_content = await msg_utils.implement_letter_edits(
            old_content, edit_instructions=self.handler.message.safe_message_body
        )
        # Turn content into pdf
        new_draft_bytes = pdf_gen.create_letter_pdf_as_bytes(new_letter_content)

        # 1. Upload file to blob storage
        full_path = blob_draft_repo.create_file_path(user.user_id)
        blob_draft_repo.upload(new_draft_bytes, full_path, "application/pdf")

        # 2. Register the draft in the DB
        draft = dbc.Draft(
            draft_id=str(uuid4()),
            user_id=user.user_id,
            created_at=self.handler.message.timestamp,
            text=new_letter_content,
            blob_path=full_path,
            address_id=old_draft.address_id,
            builds_on=old_draft.draft_id,
        )
        draft = draft_repo.add(draft)

        # Send the new draft to the user
        await self.handler.send_document(
            new_draft_bytes, filename="draft_updated.pdf", mime_type="application/pdf"
        )
        message_body = sm_repo.get_msg("edit-success")
        await self.handler.send_message(message_body)

    async def handle_show_address_book(self) -> dbc.Message:
        address_repo = repos.AddressRepository(supaclient)
        sm_repo = repos.SystemMessageRepository(supaclient)
        # Get the user's address book
        user = dbc.User(
            self.handler.message.safe_user_id, created_at=str(datetime.utcnow())
        )
        address_book = address_repo.get_user_addresses(user.user_id)

        if len(address_book) == 0:
            error_message = sm_repo.get_msg(
                "show_address_book-error-user_has_no_addresses"
            )
            return await self.handler.send_message(error_message)
        else:
            # Format and send the address book
            formatted_address_book = msg_utils.format_address_book(address_book)
            addressee: str = address_book[0].addressee  # type: ignore
            first_name: str = addressee.split(" ")[0]
            success_message = sm_repo.get_msg("show_address_book-success").format(
                formatted_address_book, first_name
            )
            return await self.handler.send_message(success_message)

    async def handle_add_address(self) -> dbc.Message | None:
        sm_repo = repos.SystemMessageRepository(supaclient)
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
        confirmation_message = sm_repo.get_msg("add_address-success").format(
            address_confirmation_format
        )

        option_confirm = sm_repo.get_msg("add_address-option-confirm")
        option_cancel = sm_repo.get_msg("add_address-option-cancel")
        return await self.handler.send_message_confirmation_request(
            main_msg=confirmation_message,
            cancel_msg=option_cancel,
            confirm_msg=option_confirm,
        )

    async def handle_add_address_callback(self) -> dbc.Message | None:
        sm_repo = repos.SystemMessageRepository(supaclient)
        address_repo = repos.AddressRepository(supaclient)

        if self.handler.message.action_confirmed:
            message_repo = repos.MessagesRepository(supaclient)
            address_repo = repos.AddressRepository(supaclient)

            # fetch the reply to the original message that contained the address
            response_to_msg_id = self.handler.message.response_to
            assert response_to_msg_id is not None, "'response_to_msg_id' can't be None"
            og_msg_response = message_repo.get(response_to_msg_id)
            assert (
                og_msg_response.response_to is not None
            ), "id for message can't be None"
            # fetch the original message with the address
            original_message = message_repo.get(og_msg_response.response_to)
            assert (
                original_message is not None
            ), "Original message retrieved in address callback is None"
            # parse the address from the original message and add it to DB
            address: dbc.Address = msg_utils.parse_new_address(
                original_message.safe_message_body
            )
            address.user_id = self.handler.message.user_id
            address = address_repo.add(address)
            response_msg = sm_repo.get_msg("add_address_callback-confirm")
        else:
            response_msg = sm_repo.get_msg("add_address_callback-cancel")
        await self.handler.edit_or_send_message(response_msg)

        if self.handler.message.action_confirmed:
            address_book = address_repo.get_user_addresses(self.handler.message.user_id)
            formatted_address_book = msg_utils.format_address_book(address_book)
            follow_up_address_book_msg = sm_repo.get_msg(
                "add_address_callback-success-follow_up"
            ).format(formatted_address_book)
            return await self.handler.send_message(follow_up_address_book_msg)
        else:
            return None

    async def handle_delete_address(self):
        sm_repo = repos.SystemMessageRepository(supaclient)
        address_repo = repos.AddressRepository(supaclient)
        user_repo = repos.UserRepository(supaclient)
        # check msg not empty
        if self.handler.message.safe_message_body == "":
            await self.handler.send_message(
                sm_repo.get_msg("delete_address-error-msg_empty")
            )
            return None

        # We first try to convert the message to an integer. If this fails, we try to find the closest match via fuzzy search
        address_repo = repos.AddressRepository(supaclient)
        address_book = address_repo.get_user_addresses(
            self.handler.message.safe_user_id
        )
        try:
            reference_idx = int(self.handler.message.safe_message_body)
        except ValueError:
            reference_idx = (
                msg_utils.fetch_closest_address_index(
                    self.handler.message.safe_message_body, address_book
                )
                + 1
            )
            logger.info(
                f"Could not convert message {self.handler.message.message_body} to int. Used fuzzy search and identified address num. {reference_idx} for deletion"
            )
        if not 0 < reference_idx <= len(address_book):
            await self.handler.send_message(
                sm_repo.get_msg("delete_address-error-invalid_idx")
            )
            return None
        address_to_delete = address_book[reference_idx - 1]
        address_repo.delete(address_to_delete.address_id)

        # Let the user know that the address was deleted
        await self.handler.send_message(sm_repo.get_msg("delete_address-success"))

        # Show the updated address book to the user
        address_repo = repos.AddressRepository(supaclient)
        unformatted_address_book = address_repo.get_user_addresses(
            self.handler.message.safe_user_id
        )
        formatted_address_book = msg_utils.format_address_book(unformatted_address_book)
        message_new_adressbook = sm_repo.get_msg(
            "delete_address-success-follow_up"
        ).format(formatted_address_book)
        await self.handler.send_message(message_new_adressbook)

    async def handle_send(self) -> None | dbc.Message:
        """Hierarch of checks:
        1. Is there a message body? (required to identify message)
        2. Does the user have a previous draft?
        3. Does the user have any addresses saved?
        """
        sm_repo = repos.SystemMessageRepository(supaclient)
        address_repo = repos.AddressRepository(supaclient)
        message_repo = repos.MessagesRepository(supaclient)
        draft_repo = repos.DraftRepository(supaclient)
        blob_draft_repo = repos.DraftBlobRepository(supaclient)

        user = dbc.User(
            self.handler.message.safe_user_id, created_at=str(datetime.utcnow())
        )

        # 1. Is message empty?
        if self.handler.message.safe_message_body == "":
            message_body = sm_repo.get_msg("send-error-msg_empty")
            await self.handler.send_message(message_body)
            return None

        # 2. Is there a previous draft?
        last_draft = draft_repo.get(
            id=None, filters={"user": user.user_id}, order={"created_at": "desc"}
        )
        if last_draft is None:
            message_body = sm_repo.get_msg("send-error-no_draft")
            await self.handler.send_message(message_body)
            return None

        # 3. Does the user have any addresses saved?
        address_book = address_repo.get_user_addresses(user.user_id)
        if address_book == []:
            message_body = sm_repo.get_msg("send-error-user_has_no_addresses")
            await self.handler.send_message(message_body)
            return None

        # Find closest matching address
        address_idx = msg_utils.fetch_closest_address_index(
            self.handler.message.safe_message_body, address_book
        )
        if address_idx == -1:
            formatted_address_book = msg_utils.format_address_book(address_book)
            message_body = sm_repo.get_msg("send-error-no_good_address_match").format(
                formatted_address_book
            )
            await self.handler.send_message(message_body)
            return None
        address = address_book[address_idx]

        # Create a letter with the address and the draft text
        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(
            last_draft.text, address  # type: ignore
        )
        # 1. Upload file to blob storage
        full_path = blob_draft_repo.create_file_path(user.user_id)
        blob_draft_repo.upload(draft_bytes, full_path, "application/pdf")

        # 2. Register the draft in the DB
        draft = dbc.Draft(
            draft_id=str(uuid4()),
            user_id=user.user_id,
            created_at=self.handler.message.timestamp,
            text=last_draft.text,
            blob_path=full_path,
            address_id=address.address_id,
            builds_on=last_draft.draft_id,
        )
        draft = draft_repo.add(draft)

        # update the user message in the DB with the draft id so we can retrieve the draft
        # later in the callback response without ambuiguity

        payment_type = "credits" if user.num_letter_credits > 0 else "direct"
        order = dbc.Order(
            order_id=str(uuid4()),
            user_id=draft.user_id,
            draft_id=draft.draft_id,
            message_id=self.handler.message.message_id,
            address_id=address.address_id,
            status="payment_pending",
            payment_type=payment_type,
        )

        self.handler.message.draft_referenced = draft.draft_id
        self.handler.message.order_referenced = order.order_id
        message_repo.update(self.handler.message)

        await self.handler.send_document(
            draft_bytes, filename="final_letter.pdf", mime_type="application/pdf"
        )

        if payment_type == "credits":
            address_formatted = msg_utils.format_address_simple(address)
            user_first_name = (
                " " + user.first_name if user.first_name is not None else ""
            )
            msg = sm_repo.get_msg("send-success-credits").format(
                user.num_letter_credits, user_first_name, address_formatted
            )
            option_confirm = sm_repo.get_msg("send-option-confirm_sending")
            option_cancel = sm_repo.get_msg("send-option-cancel_sending")
            return await self.handler.send_message_confirmation_request(
                main_msg=msg, cancel_msg=option_cancel, confirm_msg=option_confirm
            )
        elif payment_type == "direct":
            assert order.order_id is not None
            stripe_link_single_credit = stripe_payments.get_formated_stripe_link(
                num_credits=1, client_reference_id=order.order_id, one_off=True
            )
            msg = sm_repo.get_msg("send-success-one_off").format(
                stripe_link_single_credit
            )
            return await self.handler.send_message(msg)
        else:
            raise ValueError(f"Payment type {payment_type} not recognized")

    async def handle_send_callback(self):
        sm_repo = repos.SystemMessageRepository(supaclient)
        message_repo = repos.MessagesRepository(supaclient)
        if self.handler.message.action_confirmed:
            # fetch the reply to the original message that contained the address
            original_message = message_repo.get(self.handler.message.response_to)
            assert original_message.order_referenced is not None
            pingen.dispatch_order(order_id=original_message.order_referenced)
            response_msg = sm_repo.get_msg("send_callback-confirm")

        else:
            response_msg = sm_repo.get_msg("send_callback-cancel")
        await self.handler.edit_or_send_message(response_msg)

    async def handle_commmand_not_recognised(self):
        sm_repo = repos.SystemMessageRepository(supaclient)
        message_body = sm_repo.get_msg("commmand_not_recognised-success")
        await self.handler.send_message(message_body)
