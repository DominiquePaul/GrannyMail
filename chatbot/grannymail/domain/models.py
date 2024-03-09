from __future__ import annotations
import typing as t
import datetime
from dataclasses import dataclass, field

from grannymail.integrations.pingen import Pingen
from grannymail.logger import logger

if t.TYPE_CHECKING:
    from grannymail.services.unit_of_work import AbstractUnitOfWork


@dataclass
class AbstractDataTableClass:
    """
    A base data class for representing a table-like data structure with unique fields.
    Provides methods to convert the data class to a dictionary, check if all fields are empty,
    find fields that differ from another instance of the same class, and create a copy of the instance.
    """


@dataclass
class User(AbstractDataTableClass):
    # unique fields = "user_id", "email", "phone_number", "telegram_id"
    user_id: str
    created_at: str
    num_letter_credits: int = 0
    first_name: str | None = field(default=None)
    last_name: str | None = field(default=None)
    email: str | None = field(default=None)
    phone_number: str | None = field(default=None)
    telegram_id: str | None = field(default=None)
    prompt: str | None = field(default=None)

    if email is None and phone_number is None and telegram_id is None:
        raise ValueError(
            "At least one of email, phone_number, or telegram_id must be provided"
        )

    def __str__(self):
        info_parts = []
        if self.first_name is not None and self.last_name is not None:
            info_parts.append(f"{self.first_name} {self.last_name}")
        elif self.first_name is not None:
            info_parts.append(self.first_name)
        elif self.last_name is not None:
            info_parts.append(self.last_name)

        contact_info = []
        if self.email is not None:
            contact_info.append(f"email: {self.email}")
        if self.phone_number is not None:
            contact_info.append(f"phone: {self.phone_number}")
        if self.telegram_id is not None:
            contact_info.append(f"telegram: {self.telegram_id}")

        if contact_info:
            info_parts.append(f"({'; '.join(contact_info)})")

        return " ".join(info_parts)


@dataclass
class Message(AbstractDataTableClass):
    # _unique_fields: "message_id"]
    message_id: str = field(kw_only=True)
    user_id: str = field(kw_only=True)
    messaging_platform: t.Literal["WhatsApp", "Telegram"] = field(kw_only=True)
    sent_by: str = field(kw_only=True)
    message_type: str = field(kw_only=True)
    timestamp: str = field(kw_only=True)
    # Default params
    message_body: str | None = None
    memo_duration: float | None = None
    transcript: str | None = None
    attachment_mime_type: str | None = None
    command: str | None = None
    draft_referenced: str | None = None
    phone_number: str | None = None
    action_confirmed: bool | None = None
    response_to: str | None = None
    order_referenced: str | None = None

    @property
    def safe_message_body(self) -> str:
        if self.message_body is None:
            raise ValueError("Attempted to access message_body when it is None")
        return self.message_body


@dataclass
class TelegramMessage(Message):
    # _unique_fields: "message_id", "tg_message_id"
    tg_user_id: str = field(kw_only=True)
    tg_chat_id: int = field(kw_only=True)
    tg_message_id: str = field(kw_only=True)
    messaging_platform: t.Literal["WhatsApp", "Telegram"] = "Telegram"


@dataclass
class WhatsappMessage(Message):
    # _unique_fields: "message_id", "wa_mid"
    wa_mid: str | None = None
    wa_webhook_id: str | None = None
    wa_phone_number_id: str | None = None
    wa_profile_name: str | None = None
    wa_media_id: str | None = field(default=None, kw_only=True)
    wa_reference_wamid: str | None = field(default=None, kw_only=True)
    wa_reference_message_user_phone: str | None = field(default=None, kw_only=True)
    messaging_platform: t.Literal["WhatsApp", "Telegram"] = "WhatsApp"


@dataclass
class File(AbstractDataTableClass):
    # _unique_fields: "file_id"
    file_id: str
    message_id: str
    mime_type: str
    blob_path: str


@dataclass
class Address(AbstractDataTableClass):
    # _unique_fields: "address_id"
    address_id: str
    created_at: str
    user_id: str
    addressee: str
    address_line1: str
    zip: str
    city: str
    country: str
    address_line2: str | None = None

    def is_complete_address(self):
        return all(
            [
                getattr(self, field) is not None
                for field in [
                    "addressee",
                    "address_line1",
                    "zip",
                    "city",
                    "country",
                ]
            ]
        )

    def to_address_lines(self, include_country: bool) -> list[str]:
        """Converts an address dict to a list of address lines."""
        if self.is_complete_address() is False:
            logger.info(f"Tried to send letter with invalid address: {self}")
            raise ValueError("Invalid address")
        address_lines = []
        address_lines.append(self.addressee)
        address_lines.append(self.address_line1)
        if self.address_line2:
            address_lines.append(self.address_line2)
        address_lines.append(f"{self.zip} {self.city}")
        if include_country:
            address_lines.append(self.country)
        return address_lines

    def format_address_simple(self) -> str:
        formatted_message = f"{self.addressee}\n" + f"{self.address_line1}\n"

        if self.address_line2:
            formatted_message += f"{self.address_line2}\n"

        formatted_message += f"{self.zip} {self.city}\n" + f"{self.country}"

        return formatted_message

    def format_for_confirmation(self) -> str:
        """Formats an address in a way that every item is clearly understood and can be confirmed by the user

        Args:
            address (Address): the address object to be formatted

        Returns:
            str: serialised address
        """
        formatted_message = (
            f"Addressee: {self.addressee}\n" + f"Address line 1: {self.address_line1}\n"
        )

        if self.address_line2:
            formatted_message += f"Address line 2: {self.address_line2}\n"

        formatted_message += (
            f"Postal Code: {self.zip} \nCity/Town: {self.city}\n"
            + f"Country: {self.country}"
        )

        return formatted_message


@dataclass
class Draft(AbstractDataTableClass):
    # _unique_fields: "draft_id"
    draft_id: str
    user_id: str
    created_at: str
    text: str
    blob_path: str
    address_id: str | None
    builds_on: str | None


@dataclass
class Order(AbstractDataTableClass):
    # _unique_fields: "order_id"
    order_id: str
    user_id: str
    draft_id: str
    address_id: str
    message_id: str
    status: str  # payment_pending, paid, transferred
    payment_type: str  # one_off, credits

    def dispatch(self, uow: AbstractUnitOfWork):
        """Dispatches the order by sending the letter through Pingen.

        Args:
            uow (AbstractUnitOfWork): A unit of work handling database operations.

        Raises:
            Exception: If the letter cannot be sent.
        """
        try:
            pingen_client = Pingen()
            letter_bytes = uow.drafts_blob.download(self.draft_id)
            letter_name = (
                f"order_{self.order_id}_{datetime.datetime.utcnow().isoformat()}.pdf"
            )
            pingen_client.upload_and_send_letter(letter_bytes, file_name=letter_name)
            self.status = "transferred"
            uow.orders.update(self)
        except Exception as e:
            logger.error(f"Failed to dispatch order {self.order_id}: {e}")
            raise

        logger.info(f"Order {self.order_id} dispatched successfully.")


@dataclass
class Attachment(AbstractDataTableClass):
    # _unique_fields: "attachment_id"
    attachment_id: str
    file_id: str | None = None


@dataclass
class SystemMessage(AbstractDataTableClass):
    message_identifier: str
    message_body: str


MessageType = t.TypeVar("MessageType", bound=Message)
