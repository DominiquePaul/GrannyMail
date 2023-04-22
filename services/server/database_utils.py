import re 
import uuid
import pickle
import os
from dotenv import load_dotenv
import mysql.connector as database
from typing import Any
from google.cloud import storage
from io import BytesIO
from supabase import create_client, Client

load_dotenv()

def save_pickle(obj: Any, file_loc: str) -> None:
    """Saves any python object as a pickle file for fast and simple saving

    Args:
        obj (Any): the python object that you want to save
        file_loc (str): file location of the object
    """
    with open(file_loc, "wb") as handle:
        pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(file_loc: str) -> Any:
    """Load any pickle object from disk into memory

    Args:
        file_loc (str): path of pickle file to load

    Returns:
        Any: returns the python object that was stored as a pickle
    """
    with open(file_loc, "rb") as handle:
        obj = pickle.load(handle)  # nosec: B301
        return obj


##########################
### messages functions ###
##########################


class Supabase_sql_client:
    def __init__(self, url: str=os.environ.get("SUPABASE_URL"), key: str=os.environ.get("SUPABASE_KEY")):
        """Instantiates an object to query the sql database. 

        This is implemented as a class such that the same options can be called for a similar 
        class that connects to a different sql database provider

        Args:
            url (str, optional): URL of the supabase sql database. Defaults to os.environ.get("SUPABASE_URL").
            key (str, optional): secret API key (not the anon key) Key must be private. Defaults to os.environ.get("SUPABASE_KEY").
        """
        self.supabase: Client = create_client(url, key)

    def add_message(self,
        sent_by: str,
        phone_number: str,
        media_type: str,
        uid: str | None = None,
        memo_duration_secs: float | None = None,
        transcript: str | None = None,
        message_content: str | None = None,
        message_sid: str | None = None,
        transcription_level: str | None = None,
        attachment_uid: str | None = None,
    ) -> str:
        if uid is None:
            uid = str(uuid.uuid4())
        data = {"sent_by": sent_by,
                "phone_number": phone_number,
                "media_type": media_type,
                "message_id": uid,
                "memo_duration_secs": memo_duration_secs,
                "transcript": transcript,
                "message_content": message_content,
                "message_sid": message_sid,
                "transcription_level": transcription_level,
                "attachment_uid": attachment_uid
                }
        self.supabase.table("messages").insert(data).execute()
        return uid

    def get_last_x_memos(self, phone_number: str, n_memos: int) -> list:
        assert phone_number[0] == "+", "Phone number should contain a leading +"
        response = self.supabase.table('messages').select('*').eq('media_type', 'audio').eq("phone_number", phone_number).order("timestamp", desc=False).execute()
        data = response.data[0]
        return data[:n_memos]

    def get_message_by_uid(self, uid: str) -> dict:
        response = self.supabase.table('messages').select("*").eq("message_id", uid).execute()
        data = response.data
        assert len(data) > 0, f"No results found for uid {uid}"
        assert (
            len(data) == 1
        ), f"More than row found for uid {uid}. This should not be possibel for a unique identifier"
        return data[0]

    def update_message_by_uid(self, uid: str, update_dict: dict) -> None:
        self.supabase.table('messages').update(update_dict).eq("message_id", uid).execute()

    def get_last_nth_user_message(self, phone_number: str, n=0) -> dict:
        response = self.supabase.table('messages').select("*").eq("phone_number", phone_number)
        data = response.data
        if n + 1 > len(data):
            raise ValueError(
                f"Only {len(data)} messages found for that user. Cannot return the {n}th message"
            )
        return data[n]

    def get_user_uid_from_phone(self, phone_number: str) -> str:
        response = self.supabase.table('users').select("*").eq("phone_number", phone_number)
        data = response.data
        assert len(data) <= 1, "More than one user found for that phone number"
        assert len(data) == 1, "No user found for that phone number"
        return data[0]["user_id"]

    def add_address_to_user_addressbook(
        self, user_phone_number: str, address_details: dict
    ) -> None:
        response = self.supabase.table("users").select("user_id").eq("phone_number", phone_number).execute()
        address_details["user_id"] = response.data.dict()[0]["user_id"]
        self.supabase.table("address_book").insert(address_details).execute()
        
    def get_users_address_book(self, phone_number: str) -> list[dict]:
        user_id = self.get_user_uid_from_phone(phone_number)
        response = self.supabase.table("address_book").select("*").eq("user_id", user_id).execute()
        return response.data

    def add_letter_content(self, phone_number: str, letter_content: str, letter_input: str) -> None:
        pass

    def update_letter_content(self, uuid: str, update_vals: dict) -> None:
        pass
    
    def get_last_user_letter_content(self, phone_number: str) -> str | None:
        pass 

    def add_letter(self, value_dict: dict) -> None:
        self.supabase.table("letter").insert(address_details).execute()

class MySQL_client:
    def __init__(self):
        self.connection = database.connect(
            user=os.environ.get("MYSQL_USER"),
            password=os.environ.get("MYSQL_PASSWORD"),
            host=os.environ["MYSQL_HOST"],
            database=os.environ.get("MYSQL_DATABASE"),
        )

        self.cursor = self.connection.cursor(dictionary=True)

    def add_message(self,
        sent_by: str,
        phone_number: str,
        media_type: str,
        uid: str | None = None,
        memo_duration_secs: float | None = None,
        transcript: str | None = None,
        message_content: str | None = None,
        message_sid: str | None = None,
        transcription_level: str | None = None,
        attachment_uid: str | None = None,
    ) -> str:
        uid:str = uid or str(uuid.uuid4())
        statement = "INSERT INTO messages (uid, sent_by, message_content, phone_number, media_type, memo_duration_secs, transcript, message_sid, transcription_level, attachment_uid) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        data = (
            uid,
            sent_by,
            message_content,
            phone_number,
            media_type,
            memo_duration_secs,
            transcript,
            message_sid,
            transcription_level,
            attachment_uid,
        )
        self.cursor.execute(statement, data)
        self.connection.commit()
        print("Successfully added entry to database")
        return uid

    def get_last_x_memos(self, phone_number: str, n_memos: int) -> list:
        # uid_list = ', '.join(str(id) for id in longIdList)
        statement = (
            f"SELECT * FROM messages WHERE phone_number=%s AND media_type='audio' ORDER BY timestamp ASC LIMIT %s"
        )
        self.cursor.execute(statement, (phone_number, n_memos))
        results = self.cursor.fetchall()
        return results
    
    def get_message_by_uid(self, uid: str) -> dict:
        """Returns the entry of a single entry in the messages table as a dict

        Args:
            uid (str): unique identifier of the message. This ensures that only one message is returned.

        Returns:
            Dict: a dictionary of all entries for that message as key value pairs
        """
        statement = "SELECT * FROM messages WHERE c=%s"
        data = [uid]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        assert len(results) > 0, f"No results found for uid {uid}"
        assert (
            len(results) == 1
        ), f"More than row found for uid {uid}. This should not be possibel for a unique identifier"
        return results[0]

    def update_message_by_uid(self, uid: str, update_dict: dict) -> None:
        """Updates an entry in the messages table according to a dictionary

        Args:
            uid (str): unique identifier of the message in the message table
            update_dict (Dict): a dictionary where the keys represent the values to be updated and the values represent the new values
        """
        message_info_dict = self.get_message_by_uid(uid)
        # check that the keys of the update dict are a strict subset of the keys of the columns in the database
        if not set(update_dict.keys()) <= set(message_info_dict.keys()):
            erroneous_keys = set(update_dict.keys()) - set(message_info_dict.keys())
            erroneous_keys_str = ", ".join(erroneous_keys)
            raise ValueError(
                f"Some of the keys in the dictionary passed are not valid database columns: {erroneous_keys_str}"
            )
        assignments = ", ".join(f"`{k.replace('`', '``')}`=%s" for k in update_dict)
        statement = f"UPDATE messages SET {assignments}  WHERE uid = %s"
        # we merge the update valu e together with the uid as the values that need to be inserted into the sql statement
        data = list(update_dict.values()) + [uid]
        self.cursor.execute(statement, data)
        self.connection.commit()

    def get_last_nth_user_message(self, phone_number: str, n=0) -> dict:
        """Fetches the nth last message sent by the user. Indexed from 0.

        You might want to set n=1 in some case to get the last message sent by the user prior to
        the message you just received as the previous message may already have been logged.

        Args:
            phone_number (str): phone number of the user. Used to filter the messages table
            n (int, optional): The n-th last message to be returned. If its 0 it returns the last message that was logged. Defaults to 0.

        Raises:
            ValueError: Will be caused if the user requests the nth last message but there are less than n messages in the database.

        Returns:
            dict: a dictionary of all entries for the nth message as key value pairs
        """
        statement = "SELECT * FROM messages WHERE phone_number=%s AND sent_by='user' ORDER BY timestamp DESC"
        data = [phone_number]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        if n + 1 > len(results):
            raise ValueError(
                f"Only {len(results)} messages found for that user. Cannot return the {n}th message"
            )
        return results[n]

    #######################
    ### users functions ###
    #######################

    def get_user_uid_from_phone(self, phone_number: str) -> str:
        statement = "SELECT uid FROM users WHERE phone_number=%s"
        data = [phone_number]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        assert len(results) <= 1, "More than one user found for that phone number"
        assert len(results) == 1, "No user found for that phone number"
        return results[0]["uid"]

    ##############################
    ### Address book functions ###
    ##############################

    def add_address_to_user_addressbook(
        self, user_phone_number: str, address_details: dict
    ) -> None:
        # fetch users unique id
        statement = "SELECT uid FROM users WHERE phone_number=%s"
        data = [user_phone_number]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        user_uid = results[0]["uid"]

        # add address to address book
        address_details.update({"associated_user_uid": user_uid, "uid": str(uuid.uuid4())})
        statement = f"INSERT INTO address_book ({', '.join(address_details.keys())}) VALUES ({', '.join(['%s']*len(address_details.keys()))})"
        data = list(address_details.values())
        self.cursor.execute(statement, data)
        self.connection.commit()

    def get_users_address_book(self, phone_number: str) -> list[dict]:
        user_uid = self.get_user_uid_from_phone(phone_number)
        statement = "SELECT * FROM address_book WHERE associated_user_uid=%s"
        data = [user_uid]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        return results

    #################################
    ### Letter Content functions ####
    #################################

    def add_letter_content(self, phone_number: str, letter_content: str, letter_input: str) -> None:
        user_uid = self.get_user_uid_from_phone(phone_number)
        num_characters = len(letter_content)
        statement = "INSERT INTO letter_contents (uid, user_uid, num_characters, letter_content, letter_input) VALUES (%s, %s, %s, %s, %s)"
        letter_uid = str(uuid.uuid4())
        data = (letter_uid, user_uid, num_characters, letter_content, letter_input)
        self.cursor.execute(statement, data)
        self.connection.commit()
        return letter_uid

    def update_letter_content(self, uuid: str, update_vals: dict) -> None:
        statement = f"UPDATE letter_contents SET {', '.join([f'{k}=%s' for k in update_vals.keys()])} WHERE uid=%s"
        data = list(update_vals.values()) + [uuid]
        self.cursor.execute(statement, data)
        self.connection.commit()

    def get_last_user_letter_content(self, phone_number: str) -> str | None:
        user_uid = self.get_user_uid_from_phone(phone_number)

        statement = "SELECT * FROM letter_contents WHERE user_uid=%s ORDER BY timestamp DESC LIMIT 1"
        data = [user_uid]
        self.cursor.execute(statement, data)
        results = self.cursor.fetchall()
        if len(results) == 0:
            return None
        else:
            return results[0]


    #################################
    ### Letter Content functions ####
    #################################


    def add_letter(self, value_dict: dict) -> None:
        statement = f"INSERT INTO letters ({', '.join(value_dict.keys())}) VALUES ({', '.join(['%s']*len(value_dict.keys()))})"
        data = list(value_dict.values())
        self.cursor.execute(statement, data)
        self.connection.commit()




class BlobStorage:
    def __init__(
        self,
        root_folder_path: str = os.environ["BLOB_STORAGE_ROOT_FOLDER"],
        gcp_project_id: str | None = os.environ.get("GCP_PROJECT_ID", None),
        gcp_bucket_name: str | None = os.environ.get("GCP_BUCKET_NAME", None),
    ):
        self.destination = "GCP" if root_folder_path == "gcp" else "local"
        self.root_folder = (
            root_folder_path if self.destination == "local" else ""
        )
        self.letter_folder = os.path.join(self.root_folder, "letters")
        self.memo_folder = os.path.join(self.root_folder, "memos")
        if self.destination == "GCP":
            assert bool(gcp_project_id) & bool(
                gcp_bucket_name
            ), "GCP project id & project id and bucket name must be provided if using GCP"
            self.gcp_project_id = gcp_project_id
            self.gcp_bucket_name = gcp_bucket_name
            self.gcp_client = storage.Client(project=self.gcp_project_id)
            self.bucket = self.gcp_client.get_bucket(self.gcp_bucket_name)

    def __repr__(self):
        return "BlobStorage object with root folder: {}".format(self.root_folder)

    def __str__(self):
        return "BlobStorage object with root folder: {}".format(self.root_folder)

    def _write_bytes(self, filebytes, path):
        if self.destination == "local":
            with open(path, "wb") as f:
                f.write(filebytes)
        elif self.destination == "GCP":
            bytes_file = BytesIO(filebytes)
            blob = self.bucket.blob(path)
            blob.upload_from_file(bytes_file)
        else:
            assert (
                False
            ), "Should not be possible to get here. Check self.destination: {}".format(
                self.destination
            )

    def _write_pkl(self, object, path):
        if self.destination == "local":
            with open(path, "wb") as handle:
                pickle.dump(object, handle, protocol=pickle.HIGHEST_PROTOCOL)
        elif self.destination == "GCP":
            pickled_data = pickle.dumps(object)
            blob = self.bucket.blob(path)
            blob.upload_from_string(pickled_data)
        else:
            assert (
                False
            ), "Should not be possible to get here. Check self.destination: {}".format(
                self.destination
            )

    def _read_bytes(self, path: str) -> bytes:
        """wrapper for getting bytes from local or GCP

        Args:
            path (str): location/identifier of file

        Returns:
            bytes: the bytes of any file that is being retrieved
        """
        if self.destination == "local":
            with open(path, "rb") as f:
                return f.read()
        elif self.destination == "GCP":
            blob = self.bucket.get_blob(path)
            return blob.download_as_string()
        else:
            assert (
                False
            ), "Should not be possible to get here. Check self.destination: {}".format(
                self.destination
            )

    def _get_or_create_subfolder(self, folder: str, subfolder_name: str) -> str:
        """Creates a subfolder if it does not exist and returns the path

        For the case of GCP we don not need to do this as GCP automatically creates subfolders for us.
        Actually there is no such thing as a folder in GCP, only a bucket, but we can use the folder
        structure to our advantage. We do not need to create a subfolder explicitly so we just return
        the path.

        Args:
            folder (str): path to parent folder in which we want to create the subdirectory
            subfolder_name (str): Name of the subfolder that we want to create

        Returns:
            str: full path to the subfolder that can be used to store a file there without having to
                worry about getting a 'path does not exist' error
        """
        path = os.path.join(folder, subfolder_name)
        if self.destination == "local":
            if not os.path.exists(path):
                os.mkdir(path)
            else:
                print(f"Folder {path} already exists")
            return path
        elif self.destination == "GCP":
            return path
        else:
            assert (
                False
            ), "Should not be possible to get here. Check self.destination: {}".format(
                self.destination
            )

    def save_letter(self, letter_bytes: bytes, letter_id):
        path = os.path.join(self.letter_folder, letter_id)
        path += ".pdf" if path[-4:] != ".pdf" else ""
        self._write_bytes(letter_bytes, path)

    def save_letter_draft(self, text:str, letter_id):
        path = os.path.join(self.letter_folder, letter_id)
        path += ".rtf" if path[-4:] != ".rtf" else ""
        text = self._plain_text_to_rtf(text)
        self._write_bytes(text.encode(), path)  

    def save_voice_memo(self, voice_memo_bytes: bytes, unique_id: str) -> None:
        path_subfolder = self._get_or_create_subfolder(self.memo_folder, unique_id)
        path_audio = os.path.join(path_subfolder, "audio.ogg")
        self._write_bytes(voice_memo_bytes, path_audio)

    def save_whisper_pkl(self, whisper_object, unique_id: str) -> None:
        path_subfolder = self._get_or_create_subfolder(self.memo_folder, unique_id)
        path_whisper_pkl = os.path.join(path_subfolder, "whisper_object.pkl")
        self._write_pkl(whisper_object, path_whisper_pkl)

    def get_letter_as_bytes(self, letter_uid: str) -> bytes:
        path = os.path.join(self.letter_folder, letter_uid)
        path += ".pdf" if path[-4:] != ".pdf" else ""
        return self._read_bytes(path)
    
    def get_audio_as_bytes(self, uid:str) -> bytes:
        path = os.path.join(self.memo_folder, uid, "audio.ogg")
        return self._read_bytes(path)
    
    def _make_file_public(self, path:str) -> str:
        blob = self.bucket.get_blob(path)
        blob.make_public()
        public_url = blob.public_url
        return public_url
    
    def _make_file_private(self, path:str) -> None:
        blob = self.bucket.get_blob(path)
        blob.make_private()

    def _plain_text_to_rtf(self, plain_text):
        rtf_text = '{\\rtf1\\ansi\n'
        rtf_text += plain_text.replace('\n', '\\par\n')
        rtf_text += '\n}'
        return rtf_text

    def _rtf_to_plain_text(self, rtf_text:str) -> str:
        # Remove RTF control words and symbols
        plain_text = rtf_text.replace('\\par', '\n')
        plain_text = re.sub(r'\\[a-z0-9]*\d*', '', plain_text)
        plain_text = re.sub(r'\\[{}]', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s', '', plain_text)
        plain_text = re.sub(r'\\~', ' ', plain_text)
        plain_text = re.sub(r'\\=', '', plain_text)
        plain_text = re.sub(r'\\-', '', plain_text)
        plain_text = re.sub(r'\\_', '_', plain_text)
        plain_text = re.sub(r'\\\'[a-z0-9]{2}', '', plain_text)
        plain_text = re.sub(r'\\\"[a-z0-9]{2}', '', plain_text)
        plain_text = re.sub(r'\\\'[A-Z]{2}', '', plain_text)
        plain_text = re.sub(r'\\\"[A-Z]{2}', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\*', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s?\d{0,3}\s?', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s?\([A-Za-z]+\)\s?', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s?\([0-9]+\)\s?', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s?\(\d{0,3}\)\s?', '', plain_text)
        plain_text = re.sub(r'\\[A-Za-z]+\s?\{[^\}]*\}\s?', '', plain_text)

        # Remove extra whitespace
        plain_text = re.sub(r'[ \t]+\n', '\n', plain_text)
        plain_text = re.sub(r'\n\n+', '\n\n', plain_text)
        plain_text = plain_text.strip()

        return plain_text


    def set_letter_pdf_public(self, letter_uid: str) -> str:
        """Creates a public URL for a letter. This may be required to send the letter to the recipient.

        Args:
            letter_uid (str): identifier of the letter. Corresponds to the uuid in the sql database

        Returns:
            str: public url of the letter that can be accessed in a browser and specifically by the twilio API
        """
        path = os.path.join(self.letter_folder, letter_uid)
        path += ".pdf" if path[-4:] != ".pdf" else ""
        return self._make_file_public(path)

    def set_letter_pdf_private(self, letter_uid: str):
        """Set the a blob object again and remove its publice access url

        Args:
            letter_uid (str): identifier for the letter. Corresponds to the uuid in the sql database
        """
        path = os.path.join(self.letter_folder, letter_uid)
        path += ".pdf" if path[-4:] != ".pdf" else ""
        self._make_file_private(path)

    def set_letter_draft_public(self, letter_uid: str) -> str:
        """Creates a public URL for a letter. This may be required to send the letter to the recipient.

        Args:
            letter_uid (str): identifier of the letter. Corresponds to the uuid in the sql database

        Returns:
            str: public url of the letter that can be accessed in a browser and specifically by the twilio API
        """
        path = os.path.join(self.letter_folder, letter_uid)
        path += ".rtf" if path[-4:] != ".rtf" else ""
        return self._make_file_public(path)

    def set_letter_draft_private(self, letter_uid: str):
        """Set the a blob object again and remove its publice access url

        Args:
            letter_uid (str): identifier for the letter. Corresponds to the uuid in the sql database
        """
        path = os.path.join(self.letter_folder, letter_uid)
        path += ".rtf" if path[-4:] != ".rtf" else ""
        self._make_file_private(path)


if __name__ == "__main__":
    # some simple commands for development
    # uid = str(uuid.uuid4())
    # add_message(
    #     uid=uid,
    #     sent_by="debug",
    #     phone_number="41768017796",
    #     media_type="audio",
    #     memo_duration_secs=22.3,
    #     transcript="hello content",
    #     message_content="message content",
    # )

    # # check that everything worked
    # res = get_message_by_uid(uid)
    # print(res)
    # print(type(res))

    # # upate values
    # update_message_by_uid(uid, {"transcription_level": "small"})
    # print(get_message_by_uid(uid)["transcription_level"])


    # Test some functions
    update_message_by_uid(uid = "0010061e-d07c-4045-afab-9502910475d4", 
                          update_dict={
            "transcription_level": "small",
            "transcript": "hibye",
            "memo_duration_secs": 32,
        })

    add_letter_content("41768017796", "hiybe")


    # # load pdf as bytes
    # pdf_path_upload = "/Users/dominiquepaul/xProjects/02_Code23/OmiDiary/data/letters/00106968-6967-42a2-95c4-bfbf99845f59.pdf"
    # pdf_path_download = "/Users/dominiquepaul/xProjects/02_Code23/OmiDiary/data/letters/00106968-6967-42a2-95c4-bfbf99845f59_new.pdf"
    # with open(pdf_path_upload, "rb") as fr:
    #     pdf_bytes = fr.read()

    # # check blob storage:
    # blob_manager = BlobStorage()
    # example_uuid = str(uuid.uuid4())
    # print(f"Destination: {blob_manager.destination}")
    # blob_manager.save_letter(pdf_bytes, example_uuid)
    # downloaded_pdf = blob_manager.get_letter_as_bytes(example_uuid)
    # # save pdf to test
    # with open(pdf_path_download, "wb") as fw:
    #     fw.write(downloaded_pdf)

    # public_url = blob_manager.set_letter_pdf_public(example_uuid)
    # print(public_url)
    # blob_manager.set_letter_pdf_private(example_uuid)
