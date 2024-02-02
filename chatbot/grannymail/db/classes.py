from dataclasses import asdict, dataclass, field


@dataclass
class AbstractDataTableClass:
    """All dataclasses should have a _unique_fields attribute to identify the
    values in that table that must be unique. This assumption simplifies a lot
    of the implemented methods
    """

    _unique_fields: list[str]

    def to_dict(self) -> dict:
        return {
            k: v
            for k, v in asdict(self).items()
            if v is not None and k != "_unique_fields"
        }

    def is_empty(self) -> bool:
        """Returns True if all fields of the dataclass are None. Requires that None is the default value for all fields"""
        return all(
            [
                getattr(self, field) is None
                for field in self.__annotations__
                if field != "_unique_fields"
            ]
        )

    def find_different_fields(self, obj_compared) -> list:
        """Compares objec with another object of the same type and compares all fields that have changed except for fields that are None in the incoming object"""
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


@dataclass
class TelegramMessage(Message):
    tg_id: str | None = None
    tg_chat_id: str | None = None
    tg_message_id: str | None = None


@dataclass
class WhatsappMessage(Message):
    wa_mid: str | None = None
    wa_webhook_id: str | None = None
    wa_phone_number_id: str | None = None
    wa_profile_name: str | None = None
    wa_media_id: str | None = field(default=None, kw_only=True)
    wa_reference_wamid: str | None = field(default=None, kw_only=True)
    wa_reference_message_user_phone: str | None = field(default=None, kw_only=True)


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
