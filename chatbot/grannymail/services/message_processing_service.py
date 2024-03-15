from difflib import get_close_matches
import uuid

import grannymail.domain.models as m
import grannymail.integrations.pdf_gen as pdf_gen
import grannymail.integrations.stripe_payments as stripe_payments
import grannymail.utils.message_utils as msg_utils
from grannymail.domain import models as m
from grannymail.integrations.messengers import telegram, whatsapp
from grannymail.integrations.messengers.base import AbstractMessenger
from grannymail.logger import logger
from grannymail.services.unit_of_work import AbstractUnitOfWork
from grannymail.utils import utils


class NoTranscriptFound(Exception):
    def __init__(self, message):
        super().__init__(message)


class MessageProcessingService:
    def __init__(self):
        self.command_handlers = [
            method for method in dir(self) if method.startswith("handle_")
        ]

    async def receive_and_process_message(
        self,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
        update=None,
        context=None,
        data=None,
    ):
        message = await self._process_message(uow, messenger, update, context, data)

        #  For messages triggering a process we send the user a signal
        # that we are processing their request
        command_confirmations = {
            "voice": "voice-confirm",
            "edit": "edit-confirm",
        }
        if message.command in command_confirmations:
            msg_body = uow.system_messages.get_msg(
                command_confirmations[message.command]
            )
            await messenger.reply_text(message, msg_body, uow)

        assert message.command is not None, "No command, not sure how to route command"
        command_search_term = "handle_" + message.command
        if command_search_term in self.command_handlers:
            return await getattr(self, command_search_term)(message, uow, messenger)
        else:
            return await self.process_unknown_command(message, messenger, uow)

    async def process_unknown_command(
        self,
        message: m.MessageType,
        messenger: AbstractMessenger,
        uow: AbstractUnitOfWork,
    ) -> m.MessageType:
        """We want to run a fuzzy search through all commands and respond with a message
        guiding the user to fix their mistake
        """
        assert message.command is not None, "No command, not sure how to route command"
        if message.command == "_no_command":
            msg_body = uow.system_messages.get_msg("no_command-success")
        else:
            all_commands = [x.replace("handle_", "") for x in self.command_handlers]
            closest_match = get_close_matches(
                message.command, all_commands, n=1, cutoff=0.0
            )[0]
            msg_body = uow.system_messages.get_msg("unknown_command-success").format(
                closest_match
            )
        return await messenger.reply_text(message, msg_body, uow)

    async def _process_message(
        self,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
        update=None,
        context=None,
        data=None,
    ) -> m.BaseMessage:
        """Parses everything except media of a message received via Telegram/Whatsapp"""
        if isinstance(messenger, telegram.Telegram):
            assert update is not None, "Update is None"
            assert context is not None, "Context is None"
            return await messenger.process_message(update, context, uow)
        elif isinstance(messenger, whatsapp.Whatsapp):
            assert data is not None, "Data is None"
            return await messenger.process_message(data, uow)
        else:
            raise ValueError("Messenger is neither whatsapp or telegram messenger")

    async def handle_help(
        self,
        ref_message: m.MessageType,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ) -> m.MessageType:
        msg_body = uow.system_messages.get_msg("help-success")
        return await messenger.reply_text(ref_message, msg_body, uow)

    def _is_message_empty(self, message: m.BaseMessage) -> bool:
        if message.message_body is None or message.message_body.replace(" ", "") == "":
            return True
        return False

    async def handle_report_bug(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        # check that message is not empty
        msg_id = (
            "report_bug-error-msg_empty"
            if self._is_message_empty(ref_message)
            else "report_bug-success"
        )
        msg_body = uow.system_messages.get_msg(msg_id)
        await messenger.reply_text(ref_message, msg_body, uow)

    async def handle_edit_prompt(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        if self._is_message_empty(ref_message):
            msg_body = uow.system_messages.get_msg("edit_prompt-error-msg_empty")
        else:
            new_prompt = ref_message.safe_message_body

            user = uow.users.get_one(ref_message.user_id)
            user.prompt = new_prompt
            uow.users.update(user)
            msg_body = uow.system_messages.get_msg("edit_prompt-success").format(
                new_prompt
            )
        await messenger.reply_text(ref_message, msg_body, uow)

    async def handle_voice(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        """Processes all steps related to receiving a voice message

        Key steps:
        --- These steps are always the same, no matter the command
        1. Parse Message
        2. If its a voice memo or an /edit command: send a messsage to the user
            to let them know we received something _before_ processing it (the
            processing takes a bit long)
        3. Optionally: Process any media (in this case voice memo transcription
            and letter creation)
            3.1 Download media
            3.2 Upload media to our blob storage and add entry to SQL
            3.3 Transcribe voice memo
            3.4 Update message item in DB
        --- handle voice command starts
        4. Turn transcription into a letter
        5. Save letter to blob storage and add an entry in SQL
        6. Send the letter to the user
        """
        # Check memo's duration
        assert ref_message.memo_duration is not None, "Memo duration is None"
        if ref_message.memo_duration < 5:  # type: ignore
            msg_body = uow.system_messages.get_msg("voice-warning-duration")
            await messenger.reply_text(ref_message, msg_body, uow)

        # download the voice memo and transcribe it
        file = uow.files.get_one(
            id=None, filters={"message_id": ref_message.message_id}
        )
        if file is None:
            raise ValueError("No file found in DB")
        voice_bytes = uow.files_blob.download(file.blob_path)
        ref_message.transcript = await msg_utils.transcribe_voice_memo(
            voice_bytes, ref_message.memo_duration
        )

        try:
            letter_text = await msg_utils.transcript_to_letter_text(
                ref_message.transcript, ref_message.user_id, uow
            )
        except msg_utils.CharactersNotSupported as e:
            # send a message back to the user
            error_msg = uow.system_messages.get_msg(
                "voice-error-characters_not_supported"
            )
            await messenger.reply_text(ref_message, error_msg, uow)
            return None

        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(letter_text)

        ##############
        # 1. Upload file to blob storage
        blob_path = uow.drafts_blob.upload(
            draft_bytes, ref_message.user_id, "application/pdf"
        )

        # 2. Register the draft in the DB
        draft = m.Draft(
            draft_id=str(uuid.uuid4()),
            user_id=ref_message.user_id,
            created_at=ref_message.timestamp,
            text=letter_text,
            blob_path=blob_path,
            address_id=None,
            builds_on=None,
        )
        uow.drafts.add(draft)
        ####################

        # send document and message
        msg_body = uow.system_messages.get_msg("voice-success")
        await messenger.reply_document(
            ref_message, draft_bytes, "draft.pdf", "application/pdf", uow
        )
        await messenger.reply_text(ref_message, msg_body, uow)

    async def handle_edit(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        if self._is_message_empty(ref_message):
            msg_body = uow.system_messages.get_msg("edit-error-msg_empty")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        # fetch the last draft that we're editing
        old_drafts = uow.drafts.get_all(
            filters={"user_id": ref_message.user_id},
            order={"created_at": "desc"},
        )

        # If we find no previous draft we respond with an error
        if len(old_drafts) == 0:
            error_msg = uow.system_messages.get_msg("edit-error-no_draft_found")
            await messenger.reply_text(ref_message, error_msg, uow)
            return None

        old_draft = old_drafts[0]
        old_content: str = old_draft.text  # type: ignore

        # Generate the new letter content
        new_letter_content = await msg_utils.implement_letter_edits(
            old_content, edit_instructions=ref_message.safe_message_body, uow=uow
        )
        # Turn content into pdf
        new_draft_bytes = pdf_gen.create_letter_pdf_as_bytes(new_letter_content)

        # 1. Upload file to blob storage
        full_path = uow.drafts_blob.upload(
            new_draft_bytes, ref_message.user_id, "application/pdf"
        )

        # 2. Register the draft in the DB
        draft = m.Draft(
            draft_id=str(uuid.uuid4()),
            user_id=ref_message.user_id,
            created_at=ref_message.timestamp,
            text=new_letter_content,
            blob_path=full_path,
            address_id=old_draft.address_id,
            builds_on=old_draft.draft_id,
        )
        draft = uow.drafts.add(draft)

        # Send the new draft to the user
        await messenger.reply_document(
            ref_message,
            file_data=new_draft_bytes,
            filename="draft_updated.pdf",
            mime_type="application/pdf",
            uow=uow,
        )
        msg_body = uow.system_messages.get_msg("edit-success")
        await messenger.reply_text(ref_message, msg_body, uow)

    async def handle_show_address_book(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        # Get the user's address book
        address_book = uow.addresses.get_all(
            filters={"user_id": ref_message.user_id}, order={"created_at": "asc"}
        )

        if len(address_book) == 0:
            error_message = uow.system_messages.get_msg(
                "show_address_book-error-user_has_no_addresses"
            )
            return await messenger.reply_text(ref_message, error_message, uow)
        else:
            # Format and send the address book
            formatted_address_book = msg_utils.format_address_book(address_book)
            addressee: str = address_book[0].addressee  # type: ignore
            first_name: str = addressee.split(" ")[0]
            success_message = uow.system_messages.get_msg(
                "show_address_book-success"
            ).format(formatted_address_book, first_name)
            return await messenger.reply_text(ref_message, success_message, uow)

    async def handle_add_address(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        user_error_message = msg_utils.error_in_address(
            ref_message.safe_message_body, uow=uow
        )
        if user_error_message:
            error_msg = user_error_message
            await messenger.reply_text(ref_message, error_msg, uow)
            return None

        # Parse the message and add the address to the database
        # we only need this to show the user the formatted address to confirm
        address = msg_utils.parse_new_address(
            ref_message.safe_message_body,
            created_at=ref_message.timestamp,
            user_id=ref_message.user_id,
        )

        confirmation_message = uow.system_messages.get_msg(
            "add_address-success"
        ).format(address.format_for_confirmation())

        option_confirm = uow.system_messages.get_msg("add_address-option-confirm")
        option_cancel = uow.system_messages.get_msg("add_address-option-cancel")
        return await messenger.reply_buttons(
            ref_message=ref_message,
            main_msg=confirmation_message,
            cancel_msg=option_cancel,
            confirm_msg=option_confirm,
            uow=uow,
        )

    async def handle_add_address_callback(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        if ref_message.action_confirmed:
            # fetch the reply to the original message that contained the address
            response_to_msg_id = ref_message.response_to
            assert response_to_msg_id is not None, "'response_to_msg_id' can't be None"
            og_msg_response = uow.messages.get_one(response_to_msg_id)
            assert (
                og_msg_response.response_to is not None
            ), "id for message can't be None"
            # fetch the original message with the address
            original_message = uow.messages.get_one(og_msg_response.response_to)
            assert (
                original_message is not None
            ), "Original message retrieved in address callback is None"
            # parse the address from the original message and add it to DB
            address: m.Address = msg_utils.parse_new_address(
                original_message.safe_message_body,
                created_at=original_message.timestamp,
                user_id=original_message.user_id,
            )
            address.user_id = ref_message.user_id
            address = uow.addresses.add(address)
            response_msg = uow.system_messages.get_msg("add_address_callback-confirm")
        else:
            response_msg = uow.system_messages.get_msg("add_address_callback-cancel")
        await messenger.reply_edit_or_text(ref_message, response_msg, uow)

        if ref_message.action_confirmed:
            address_book = uow.addresses.get_all(
                filters={"user_id": ref_message.user_id}, order={"created_at": "asc"}
            )
            formatted_address_book = msg_utils.format_address_book(address_book)
            follow_up_address_book_msg = uow.system_messages.get_msg(
                "add_address_callback-success-follow_up"
            ).format(formatted_address_book)
            return await messenger.reply_text(
                ref_message, follow_up_address_book_msg, uow
            )
        else:
            return None

    async def handle_delete_address(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        # check msg not empty
        if ref_message.safe_message_body == "":
            msg_body = uow.system_messages.get_msg("delete_address-error-msg_empty")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        # We first try to convert the message to an integer. If this fails, we try to find the closest match via fuzzy search
        address_book = uow.addresses.get_all(
            filters={"user_id": ref_message.user_id}, order={"created_at": "asc"}
        )
        try:
            reference_idx = int(ref_message.safe_message_body)
        except ValueError:
            reference_idx = (
                msg_utils.fetch_closest_address_index(
                    ref_message.safe_message_body, address_book
                )
                + 1
            )
            logger.info(
                f"Could not convert message {ref_message.safe_message_body} to int. Used fuzzy search and identified address num. {reference_idx} for deletion"
            )

        if not 0 < reference_idx <= len(address_book):
            msg_body = uow.system_messages.get_msg("delete_address-error-invalid_idx")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        address_to_delete = address_book[reference_idx - 1]
        uow.addresses.delete(address_to_delete.address_id)
        # Let the user know that the address was deleted
        msg_body = uow.system_messages.get_msg("delete_address-success")
        await messenger.reply_text(ref_message, msg_body, uow)

        # Show the updated address book to the user
        unformatted_address_book = uow.addresses.get_all(
            filters={"user_id": ref_message.user_id}, order={"created_at": "asc"}
        )
        formatted_address_book = msg_utils.format_address_book(unformatted_address_book)
        message_new_adressbook = uow.system_messages.get_msg(
            "delete_address-success-follow_up"
        ).format(formatted_address_book)
        await messenger.reply_text(ref_message, message_new_adressbook, uow)

    async def handle_send(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        """Hierarch of checks:
        1. Is there a message body? (required to identify message)
        2. Does the user have a previous draft?
        3. Does the user have any addresses saved?
        """
        user = uow.users.get_one(ref_message.user_id)

        # 1. Is message empty?
        if self._is_message_empty(ref_message):
            msg_body = uow.system_messages.get_msg("send-error-msg_empty")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        # 2. Is there a previous draft?
        all_drafts = uow.drafts.get_all(
            filters={"user_id": ref_message.user_id}, order={"created_at": "desc"}
        )
        if not all_drafts:
            msg_body = uow.system_messages.get_msg("send-error-no_draft")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        # 3. Does the user have any addresses saved?
        address_book = uow.addresses.get_all(
            filters={"user_id": ref_message.user_id}, order={"created_at": "asc"}
        )
        if address_book == []:
            msg_body = uow.system_messages.get_msg("send-error-user_has_no_addresses")
            await messenger.reply_text(ref_message, msg_body, uow)
            return None

        # Find closest matching address
        address_idx = msg_utils.fetch_closest_address_index(
            ref_message.safe_message_body, address_book
        )
        if address_idx == -1:
            formatted_address_book = msg_utils.format_address_book(address_book)
            msg_body = uow.system_messages.get_msg(
                "send-error-no_good_address_match"
            ).format(formatted_address_book)
            await messenger.reply_text(ref_message, msg_body, uow)
            return None
        address = address_book[address_idx]

        # Create a letter with the address and the draft text
        last_draft = all_drafts[0]
        draft_bytes = pdf_gen.create_letter_pdf_as_bytes(
            last_draft.text, address  # type: ignore
        )
        # 1. Upload file to blob storage
        full_path = uow.drafts_blob.upload(draft_bytes, user.user_id, "application/pdf")

        # 2. Register the draft in the DB
        draft = m.Draft(
            draft_id=str(uuid.uuid4()),
            user_id=user.user_id,
            created_at=ref_message.timestamp,
            text=last_draft.text,
            blob_path=full_path,
            address_id=address.address_id,
            builds_on=last_draft.draft_id,
        )
        draft = uow.drafts.add(draft)

        # update the user message in the DB with the draft id so we can retrieve the draft
        # later in the callback response without ambuiguity

        payment_type = "credits" if user.num_letter_credits > 0 else "direct"
        order = m.Order(
            order_id=str(uuid.uuid4()),
            user_id=draft.user_id,
            draft_id=draft.draft_id,
            message_id=ref_message.message_id,
            address_id=address.address_id,
            status="payment_pending",
            payment_type=payment_type,
            blob_path=draft.blob_path,
        )
        uow.orders.add(order)

        ref_message.draft_referenced = draft.draft_id
        ref_message.order_referenced = order.order_id
        uow.messages.update(ref_message)

        await messenger.reply_document(
            ref_message,
            draft_bytes,
            filename="final_letter.pdf",
            mime_type="application/pdf",
            uow=uow,
        )

        if payment_type == "credits":
            user_first_name = (
                " " + user.first_name if user.first_name is not None else ""
            )
            msg_body = uow.system_messages.get_msg("send-success-credits").format(
                user_first_name,
                user.num_letter_credits,
                address.format_address_as_string(),
            )
            option_confirm = uow.system_messages.get_msg("send-option-confirm_sending")
            option_cancel = uow.system_messages.get_msg("send-option-cancel_sending")
            return await messenger.reply_buttons(
                ref_message=ref_message,
                main_msg=msg_body,
                cancel_msg=option_cancel,
                confirm_msg=option_confirm,
                uow=uow,
            )
        elif payment_type == "direct":
            assert order.order_id is not None
            stripe_link_single_credit = stripe_payments.get_formatted_stripe_link(
                num_credits=1, client_reference_id=order.order_id
            )
            stripe_5_credit_link = stripe_payments.get_formatted_stripe_link(
                num_credits=5, client_reference_id=order.order_id
            )
            stripe_10_credit_link = stripe_payments.get_formatted_stripe_link(
                num_credits=10, client_reference_id=order.order_id
            )
            msg_body = uow.system_messages.get_msg("send-success-one_off").format(
                stripe_link_single_credit, stripe_5_credit_link, stripe_10_credit_link
            )
            return await messenger.reply_text(ref_message, msg_body, uow)
        else:
            raise ValueError(f"Payment type {payment_type} not recognized")

    async def handle_send_callback(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        if ref_message.action_confirmed:
            # fetch the reply to the original message that contained the address
            response_to_og_send_message = uow.messages.get_one(ref_message.response_to)
            assert (
                response_to_og_send_message.order_referenced is not None
            ), "No order referenced in message"
            order: m.Order = uow.orders.get_one(
                response_to_og_send_message.order_referenced
            )
            order.dispatch(uow=uow)
            msg_body = uow.system_messages.get_msg("send_callback-confirm")

        else:
            msg_body = uow.system_messages.get_msg("send_callback-cancel")
        await messenger.reply_edit_or_text(ref_message, msg_body, uow)

    async def handle_commmand_not_recognised(
        self,
        ref_message: m.BaseMessage,
        uow: AbstractUnitOfWork,
        messenger: AbstractMessenger,
    ):
        msg_body = uow.system_messages.get_msg("commmand_not_recognised-success")
        await messenger.reply_text(ref_message, msg_body, uow)
