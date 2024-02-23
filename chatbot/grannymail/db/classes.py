from dataclasses import asdict, dataclass, field
import typing as t


@dataclass
class AbstractDataTableClass:
    """
    A base data class for representing a table-like data structure with unique fields.
    Provides methods to convert the data class to a dictionary, check if all fields are empty,
    find fields that differ from another instance of the same class, and create a copy of the instance.
    """

    _unique_fields: list[str]

    def to_dict(self) -> dict:
        """Converts the data class instance to a dictionary, excluding None values and the _unique_fields attribute."""
        return {
            k: v
            for k, v in asdict(self).items()
            if v is not None and k != "_unique_fields"
        }

    def is_empty(self) -> bool:
        """
        Checks if all fields in the data class are None, excluding the _unique_fields attribute.
        Requires that None is the default value for all fields.

        Returns:
            bool: True if all fields are None, False otherwise.
        """
        return all(
            [
                getattr(self, field) is None
                for field in self.__annotations__
                if field != "_unique_fields"
            ]
        )

    def find_different_fields(self, obj_compared: "AbstractDataTableClass") -> list:
        """
        Compares the current instance with another object of the same type to identify differing fields.
        Fields that are None in the incoming object are ignored in the comparison.

        Args:
            obj_compared: The object to compare against.

        Returns:
            list: A list of field names that have different values between the two objects.

        Raises:
            TypeError: If obj_compared is not an instance of AbstractDataTableClass.
            ValueError: If the two objects do not have the same fields.
        """
        differing_fields = []
        if not isinstance(obj_compared, AbstractDataTableClass):
            raise TypeError(
                f"Expected an object of type AbstractDataTableClass. Instead got {type(obj_compared)}"
            )
        if self.__annotations__ != obj_compared.__annotations__:
            raise ValueError("The two objects must have the same fields")
        for field_name in self.__annotations__:
            if getattr(obj_compared, field_name) is None:
                continue
            if getattr(self, field_name) != getattr(obj_compared, field_name):
                differing_fields.append(field_name)
        return differing_fields

    def copy(self):
        """
        Creates a deep copy of the current instance.

        Returns:
            A new instance of the same class with copied attributes.
        """
        # Use the __dict__ attribute to get all attributes and their values
        new_instance = type(self).__new__(type(self))
        new_instance.__dict__ = self.__dict__.copy()
        return new_instance


@dataclass
class User(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["user_id", "email", "phone_number", "telegram_id"],
        kw_only=True,
    )
    user_id: str | None = field(default=None)
    created_at: str | None = field(default=None)
    first_name: str | None = field(default=None)
    last_name: str | None = field(default=None)
    email: str | None = field(default=None)
    phone_number: str | None = field(default=None)
    telegram_id: str | None = field(default=None)
    prompt: str | None = field(default=None)


@dataclass
class Message(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["message_id"], kw_only=True
    )
    user_id: str | None = None
    sent_by: str | None = None
    message_id: str | None = None
    timestamp: str | None = None
    message_body: str | None = None
    memo_duration: float | None = None
    transcript: str | None = None
    attachment_mime_type: str | None = None
    command: str | None = None
    draft_referenced: str | None = None
    message_type: str | None = None
    phone_number: str | None = None
    action_confirmed: bool | None = None
    response_to: str | None = None
    messaging_platform: str | None = None

    @property
    def safe_message_body(self) -> str:
        if self.message_body is None:
            raise ValueError("Attempted to access message_body when it is None")
        return self.message_body

    @property
    def safe_user_id(self) -> str:
        if self.user_id is None:
            raise ValueError("Attempted to access user_id when it is None")
        return self.user_id


@dataclass
class TelegramMessage(Message):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["message_id", "tg_message_id"], kw_only=True
    )
    tg_user_id: str | None = None
    tg_chat_id: str | None = None
    tg_message_id: str | None = None
    messaging_platform: str = "Telegram"


@dataclass
class WhatsappMessage(Message):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["message_id", "wa_mid"], kw_only=True
    )
    wa_mid: str | None = None
    wa_webhook_id: str | None = None
    wa_phone_number_id: str | None = None
    wa_profile_name: str | None = None
    wa_media_id: str | None = field(default=None, kw_only=True)
    wa_reference_wamid: str | None = field(default=None, kw_only=True)
    wa_reference_message_user_phone: str | None = field(default=None, kw_only=True)
    messaging_platform: str = "WhatsApp"


@dataclass
class File(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["file_id"], kw_only=True)
    file_id: str | None = None
    message_id: str | None = None
    mime_type: str | None = None
    blob_path: str | None = None


@dataclass
class Address(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["address_id"], kw_only=True
    )
    created_at: str | None = None
    address_id: str | None = None
    user_id: str | None = None
    addressee: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None

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


@dataclass
class Draft(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["draft_id"], kw_only=True
    )
    draft_id: str | None = None
    user_id: str | None = None
    created_at: str | None = None
    text: str | None = None
    blob_path: str | None = None
    address_id: str | None = None
    builds_on: str | None = None


@dataclass
class Order(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["order_id"], kw_only=True
    )
    user_id: str | None = None
    draft_id: str | None = None
    address_id: str | None = None
    blob_path: str | None = None
    order_id: str | None = None
    created_at: str | None = None
    price: float | None = None


@dataclass
class Attachment(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["attachment_id"], kw_only=True
    )
    attachment_id: str | None = None
    file_id: str | None = None


@dataclass
class Changelog(AbstractDataTableClass):
    _unique_fields: list[str] = field(
        default_factory=lambda: ["changelog_id"], kw_only=True
    )
    changelog_id: str | None = None
    timestamp: str | None = None
    table_name: str | None = None
    row_id: str | None = None
    column_name: str | None = None
    column_type: str | None = None
    old_value: str | None = None
    new_value: str | None = None
