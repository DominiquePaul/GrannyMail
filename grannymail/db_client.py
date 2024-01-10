import grannymail.config as cfg
from dataclasses import dataclass, asdict, field
from supabase import create_client, Client
from datetime import datetime


class NoEntryFoundError(Exception):
    def __init__(self, key: str, data: str | float | int) -> None:
        self.message = f"No entry found in the database for searching for {key} = {data}"
        super().__init__(self.message)


@dataclass
class AbstractDataTableClass:
    """All dataclasses should have a _unique_fields attribute to identify the
    values in that table that must be unique. This assumption simplifies a lot
    of the implemented methods
    """
    _unique_fields: list[str] = field(default_factory=lambda: [])

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None and k != "_unique_fields"}

    def is_empty(self) -> bool:
        """Returns True if all fields of the dataclass are None. Requires that None is the default value for all fields
        """
        return all([getattr(self, field) is None for field in self.__annotations__ if field != "_unique_fields"])


@dataclass()
class User(AbstractDataTableClass):
    user_id: str | None = field(default=None)
    created_at: datetime | None = field(default=None)
    first_name: str | None = field(default=None)
    last_name: str | None = field(default=None)
    email: str | None = field(default=None)
    phone_number: str | None = field(default=None)
    telegram_id: str | None = field(default=None)
    _unique_fields: list[str] = field(default_factory=lambda: [
        "user_id", "email", "phone_number", "telegram_id"
    ])


@dataclass
class Message(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["message_id"])
    message_id: str | None = None
    user_id: str | None = None
    timestamp: datetime | None = None
    sent_by: str | None = None
    message: str | None = None
    memo_duration: float | None = None
    transcript: str | None = None
    mime_type: str | None = None


@dataclass()
class File(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["file_id"])
    file_id: str | None = None
    message_id: str | None = None
    mime_type: str | None = None
    blob_url: str | None = None


@dataclass()
class Address(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["address_id"])
    address_id: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    addressee: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None

    def is_complete_address(self):
        return all([getattr(self, field) is not None for field in [
            "addressee",
            "address_line1",
            "zip",
            "city",
            "country",
        ]])


@dataclass()
class Draft(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["draft_id"])
    draft_id: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    text: str | None = None


@dataclass()
class Letter(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["letter_id"])
    letter_id: str | None = None
    user_id: str | None = None
    draft_id: str | None = None
    address_id: str | None = None
    created_at: datetime | None = None
    blob_url: str | None = None
    is_sent: bool | None = None
    price: float | None = None


@dataclass()
class Attachment(AbstractDataTableClass):
    _unique_fields: list[str] = field(default_factory=lambda: ["draft_id"])
    draft_id: str | None = None
    file_id: str | None = None


class SupabaseClient:
    def __init__(
        self,
        url: str = cfg.SUPABASE_URL,
        key: str = cfg.SUPABASE_KEY,
        bucket=cfg.SUPABASE_BUCKET_NAME
    ):
        """Instantiates an object to query the sql database.

        This is implemented as a class such that the same options can be called for a similar
        class that connects to a different sql database provider

        Args:
            url (str, optional): URL of the supabase sql database. Defaults 
                to os.environ.get("SUPABASE_URL").
            key (str, optional): secret API key (not the anon key) Key must be private. 
                Defaults to os.environ.get("SUPABASE_KEY").
        """
        self.client: Client = create_client(url, key)
        self.bucket = bucket

    def _check_duplicates(self, table: str, data: AbstractDataTableClass) -> list:
        """Checks for a set of column values whether they already exist in the database

        Args:
            table (str): the DB table to search through
            values (dict): the values to search for. For convenience the entire set of data 
                that should be added to the table can be passed here.
            keys (list): the keys of the values dict that should actually checked for existence. 
                The values in the list are expected to be found as keys in the values dict and as 
                    columns in the table.

        Returns:
            list: the keys/columns with the values already in the table
        """
        duplicated_values = []
        data_dict = data.to_dict()
        for key in data._unique_fields:
            if key in data_dict.keys():
                response = (
                    self.client.table(table).select(
                        "*").eq(key, data_dict[key]).execute()
                )
                if response.data != []:
                    duplicated_values.append(key)
        return duplicated_values

    def _validate_supabase_respones(self, response: list, field_name: str, field_value: str | float | int) -> None:
        if not isinstance(response, list):
            raise ValueError(
                f"Response from Supabase was not a list. Instead got {type(response)}")
        if len(response) != 1:
            if len(response) == 0:
                raise NoEntryFoundError(field_name, field_value)
            else:
                raise ValueError(
                    f"More than one user found with {field_name} {field_value}")

    def _get_obj_info(self, table: str, obj: AbstractDataTableClass) -> dict:
        """Completes the information of an object from the database by searching for its unique values"""
        if not isinstance(obj, AbstractDataTableClass):
            raise ValueError(
                f"Expected an object of type AbstractDataTableClass. Instead got {type(obj)}")
        unique_fields = [
            field for field in obj._unique_fields if getattr(obj, field) is not None]
        if len(unique_fields) == 0:
            raise ValueError(
                f"Object of type {type(obj)} does not have any unique fields that can used to search for an entry")
        else:
            unique_field = unique_fields[0]
            response = self.client.table(table).select(
                "*").eq(unique_field, getattr(obj, unique_field)).execute().data
            self._validate_supabase_respones(
                response, unique_field, getattr(obj, unique_field))
            return response[0]

    def get_user(self, data: User) -> User:
        """Completes User information by retrieving full record from the database

        Args:
            data (User): An object of type User. The object must have at 
            least one value that is unique in the database and that can be 
            used to find the record.

        Returns:
            User: The user augmented with all the information from the database
        """
        return User(**self._get_obj_info("users", data))

    def add_user(self, user: User) -> tuple[int, str]:
        """Adds a user to the database

        Args:
            first_name (str): first name of the user
            last_name (str): last name of the user
            phone_number (str): phone number of the user
        """
        duplicates = self._check_duplicates("users", user)
        if duplicates:
            return 1, f"A existing user was already found with {', '.join(duplicates)}"
        else:
            r = self.client.table("users").insert(user.to_dict()).execute()
            print(
                "DEBUG: add user, what does the response of supabase look like after adding a user?")
            print(r)
            print(type(r))
            print(dir(r))
            return 0, "User added successfully"

    def update_user(self, user_data: User, user_update: User) -> tuple[int, str]:
        """Updates a user in the database

        Args:
            user_data (User): The user data to update. The user data must contain the user_id
        """
        user_data_full = self.get_user(user_data)

        self.client.table("users").update(user_update.to_dict()).eq(
            "user_id", user_data_full.user_id).execute()
        return 0, "User updated successfully"

    def delete_user(self, user: User) -> tuple[int, str]:
        """Deletes a user from the database

        Args:
            user (User): The user data to delete. The user data must contain the user_id
        """
        user_full = self.get_user(user)
        self.client.table("users").delete().eq(
            "user_id", user_full.user_id).execute()
        return 0, "User deleted successfully"

    def get_message(self, message: Message) -> Message:
        """Completes User information by retrieving full record from the database

        Args:
            data (Message): An object of type Message. The object must have at 
            least one value that is unique in the database and that can be 
            used to find the record.

        Returns:
            User: The Message data augmented with all the information from the database
        """
        return Message(**self._get_obj_info("messages", message))

    def get_all_user_messages(self, user: User) -> list[Message]:
        user = self.get_user(user)
        response = (
            self.client.table("messages")
            .select("*")
            .eq("user_id", user.user_id)
            .order("timestamp", desc=False)
            .execute()
        )
        data = response.data
        message_list: list[Message] = [Message(**message) for message in data]
        return message_list

    def add_message(self, msg_data: Message) -> tuple[int, str]:
        duplicates = self._check_duplicates("messages", msg_data)
        if duplicates:
            return 1, f"A existing user was already found with {', '.join(duplicates)}"
        else:
            self.client.table("messages").insert(
                msg_data.to_dict()).execute()
        return 0, "Message added successfully"

    def get_file(self, data: File) -> File:
        """Completes User information by retrieving full record from the database

        Args:
            data (Message): An object of type Message. The object must have at 
            least one value that is unique in the database and that can be 
            used to find the record.

        Returns:
            User: The Message data augmented with all the information from the database
        """
        return File(**self._get_obj_info("files", data))

    def add_file(self, file: File):
        duplicates = self._check_duplicates("files", file)
        if duplicates:
            return 1, f"A existing file was already found with {', '.join(duplicates)}"
        else:
            self.client.table("files").insert(
                file.to_dict()).execute()
        return 0, "File added successfully"

    def get_user_addresses(self, user: User) -> list[Address]:
        user = self.get_user(user)
        if user.user_id is None:
            raise ValueError(
                "User does not have a user_id. Cannot retrieve addresses")
        response = (
            self.client.table("addresses")
            .select("*")
            .eq("user_id", user.user_id)
            .order("created_at", desc=False)
            .execute()
        ).data
        address_list: list[Address] = [
            Address(**address) for address in response]
        return address_list

    def add_address(self, address: Address) -> tuple[int, str]:
        if address.user_id is None:
            raise ValueError(
                "Address does not have a user_id. Cannot add address")
        self.client.table("addresses").insert(address.to_dict()).execute()
        return 0, "Address added successfully"

    def delete_address(self, address: Address) -> tuple[int, str]:
        (self.client.table('addresses')
         .delete()
         .eq('address_id', address.address_id)
         .execute())
        return 0, "Address deleted successfully"

    def get_user_drafts(self, user: User) -> list[Draft]:
        user = self.get_user(user)
        if user.user_id is None:
            raise ValueError(
                "User does not have a user_id. Cannot retrieve addresses")
        response = (
            self.client.table("drafts")
            .select("*")
            .eq("user_id", user.user_id)
            .order("created_at", desc=False)
            .execute()
        )
        data = response.data
        self._validate_supabase_respones(data, "user_id", user.user_id)
        draft_list: list[Draft] = [Draft(**draft) for draft in data]
        return draft_list

    def get_last_draft(self, user: User) -> Draft:
        return self.get_user_drafts(user)[-1]

    def add_draft(self, draft: Draft) -> tuple[int, str]:
        self.client.table("drafts").insert(draft.to_dict()).execute()
        return 0, "Draft added successfully"

    def add_attachment(self, attachment: Attachment) -> tuple[int, str]:
        self.client.table("attachments").insert(attachment.to_dict()).execute()
        return 0, "Draft added successfully"

    def add_letter(self, letter: Letter) -> tuple[int, str]:
        self.client.table("letters").insert(letter.to_dict()).execute()
        return 0, "Letter added successfully"

    # ---------------

    def upload_file(self, filebytes: bytes, user_id: str, mime_type: str) -> str:
        if mime_type == "audio/ogg":
            suffix = ".ogg"
        else:
            raise ValueError(
                f"mime_type {mime_type} not supported for file upload")
        # create file name based on user_id and timestamp
        bucket_path = f"memos/{user_id}/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{suffix}"
        # upload to supabase storage
        self.client.storage.from_(self.bucket).upload(file=filebytes,
                                                      path=bucket_path,
                                                      file_options={"content-type": mime_type})

        return bucket_path

    def register_voice_memo(self, filebytes: bytes, message: Message):
        if message.user_id is None:
            raise ValueError(
                "Message does not have a user_id. Cannot register voice memo")
        # upload to supabase storage
        mime_type = "audio/ogg"
        bucket_path = self.upload_file(
            filebytes, message.user_id, mime_type=mime_type)
        file = File(message_id=message.message_id,
                    mime_type=mime_type, blob_url=bucket_path)
        self.add_file(file)

    def register_message(self, telegram_id: str, sent_by: str, mime_type: str, msg_text: str | None, transcript: str | None) -> Message:
        """Registers a message in the database

        Args:
            telegram_id (str): The telegram_id of the user that sent the message
            sent_by (str): Whether the message was sent by the user or the bot
            mime_type (str): The mime_type of the message
            message (str): The message itself

        Returns:
            Message: The message object with all the information from the database
        """
        user = User(telegram_id=telegram_id)
        user = self.get_user(user)
        message = Message(user_id=user.user_id,
                          sent_by=sent_by,
                          message=msg_text,
                          mime_type=mime_type,
                          transcript=transcript)
        self.add_message(message)
        return message

    # def get_last_x_memos(self, phone_number: str, n_memos: int) -> list:
    #     assert phone_number[0] != "+", "Phone number should not contain a leading +"
    #     user_id = self.get_user_uid_from_phone(phone_number)
    #     response = (
    #         self.client.table("messages")
    #         .select("*")
    #         .eq("media_type", "audio")
    #         .eq("user_id", user_id)
    #         .order("timestamp", desc=False)
    #         .execute()
    #     )
    #     data = response.data
    #     return data[:n_memos]

    # def update_message_by_uid(self, uid: str, update_dict: dict) -> None:
    #     self.client.table("messages").update(update_dict).eq(
    #         "message_id", uid
    #     ).execute()

    # def get_last_nth_user_message(self, phone_number: str, n=0) -> dict:
    #     user_id = self.get_user_uid_from_phone(phone_number)
    #     response = (
    #         self.client.table("messages")
    #         .select("*")
    #         .eq("user_id", user_id)
    #         .order("timestamp", desc=True)
    #         .execute()
    #     )
    #     data = response.data
    #     if n + 1 > len(data):
    #         raise ValueError(
    #             f"Only {len(data)} messages found for that user. Cannot return the {n}th message"
    #         )
    #     return data[n]

    # # def get_user_uid_from_phone(self, phone_number: str) -> str:
    # #     data = self.client.table("users").select(
    # #         "*").eq("phone_number", phone_number).execute().data
    # #     assert len(data) <= 1, "More than one user found for that phone number"
    # #     assert len(data) == 1, "No user found for that phone number"
    # #     return data[0]["user_id"]

    # def add_address_to_user_addressbook(
    #     self, phone_number: str, address_details: dict
    # ) -> None:
    #     response = (
    #         self.client.table("users")
    #         .select("*")
    #         .eq("phone_number", phone_number)
    #         .execute()
    #     )
    #     address_details["user_id"] = response.data[0]["user_id"]
    #     self.client.table("address_book").insert(address_details).execute()

    # def get_users_address_book(self, phone_number: str) -> list[dict]:
    #     user_id = self.get_user_uid_from_phone(phone_number)
    #     response = (
    #         self.client.table("address_book")
    #         .select("*")
    #         .eq("user_id", user_id)
    #         .execute()
    #     )
    #     return response.data

    # def add_letter(self, value_dict: dict) -> str:
    #     value_dict.update({"letter_id": letter_id})
    #     self.client.table("letters").insert(value_dict).execute()
    #     return letter_id

    # def get_users_last_letter_content(self, phone_number: str) -> dict:
    #     user_id = self.get_user_uid_from_phone(phone_number)
    #     response = (
    #         self.client.table("letters").select(
    #             "*").eq("user_id", user_id).execute()
    #     ).data
    #     assert len(response) > 0, "User has no previous letter"
    #     last_letter_content: dict = response[-1]
    #     return last_letter_content

    # def update_letter_content(self, letter_id: str, update_vals: dict) -> None:
    #     self.client.table("letters").update(update_vals).eq(
    #         "letter_id", letter_id
    #     ).execute()

    # def delete_table_contents(self, table_name):
    #     id_col_name = list(self.client.table(
    #         table_name).select("*").execute().data[0].keys())[0]
    #     res = input(
    #         f"Are you sure you want to delete the table {table_name}? Type DELETE to confirm: ")
    #     if res == "DELETE":
    #         self.client.table(table_name).delete().neq(
    #             id_col_name, uid).execute()
    #         print("Table deleted")
    #     else:
    #         print("Aborting delete operation")

    # def delete_all_tables(self):
    #     # uid = str(uuid4())
    #     res = input(
    #         f"Are you sure you want to delete ALL TABLES? Type 'YES, DELETE ALL' to confirm: ")
    #     if res == "YES, DELETE ALL":
    #         for table_name in ["letters", "address_book", "messages", "users"]:
    #             id_col_name = list(self.client.table(
    #                 table_name).select("*").execute().data[0].keys())[0]
    #             self.client.table(table_name).delete().neq(
    #                 id_col_name, uid).execute()
    #             print(f"{table_name} deleted")
    #     else:
    #         print("Aborting delete operation")
