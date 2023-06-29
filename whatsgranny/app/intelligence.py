import os
import time

import requests
import openai
from dotenv import load_dotenv
from twilio.rest import Client

import whatsgranny.app.pdf_gen as pdf_gen
import whatsgranny.app.database_utils as dbu
from whatsgranny.app.whisper_mod import transcribe

load_dotenv()
blob_manager = dbu.BlobStorage()
sql_client = dbu.Supabase_sql_client()


# the whisper model that will transcribe the voice memo. Options are [tiny, base, small, medium,
# MODEL_SIZE = os.environ["MODEL_SIZE"]
# MODEL = whisper.load_model(MODEL_SIZE, download_root="whisper_models")
# openai.api_key = os.environ["OPENAI_KEY"]

SYSTEM_INSTRUCTIONS = "Du bist ein hilfreicher und freundlicher assistent, der nutzern dabei hilft unstruktierte notizen zu einem Brief für ihre Oma zusammenzufassen"
PROMPT = "Ich schreibe einen Brief an meine Oma. Der Name meiner Oma ist Doris. Ich nenne sie häufiger Omi. Schreibe bitte einen Brief an sie aus meiner perspektive, der folgende inhalte zusammenfasst: \n\n"

# Twilio client that allows you to send messages
twilio_client = Client(
    os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
)


def send_message(msg: str, phone_number: str, save_to_db=True):
    """Send a text message to a phone number via whatsapp

    The function also logs the message to the applications's messages database. If you're in sandbox mode you the phone number needs to have to consented to receiving messages from you.

    Args:
        msg (str): _description_
        phone_number (str): the phone number to send the message to.
        save_to_db (bool, optional): Whether or not the message shoudl be logged to the database of messages. For experimentation, while you don't have a database, you might want to set this to False. Defaults to True.

    Returns:
        _type_: _description_
    """
    message = twilio_client.messages.create(
        body=msg,
        from_=f"whatsapp:{os.environ.get('TWILIO_PHONE_NUMBER')}",
        to=f"whatsapp:+{phone_number}",
    )
    # optionally log the message to the messages database
    if save_to_db:
        sql_client.add_message(
            phone_number=phone_number,
            media_type="text",
            sent_by="system",
            message_content=msg,
        )
    print(f"Add this type to the send message function {type(message)}")
    return message


def send_attachment(
    public_media_url: str,
    phone_number: str,
    msg_body: str = "",
    save_to_db=True,
    letter_uid=None,
):
    message = twilio_client.messages.create(
        body=msg_body,
        from_=f"whatsapp:{os.environ.get('TWILIO_PHONE_NUMBER')}",
        to=f"whatsapp:+{phone_number}",
        media_url=public_media_url,
    )
    assert (
        message.error_code is None
    ), f"Twilio message failed with error code {message.error_code}: {message.error_message}"
    if save_to_db:
        if letter_uid is None:
            raise ValueError(
                "Need to supply letter_uid if save_to_db is True, but none was passed"
            )
        else:
            sql_client.add_message(
                phone_number=phone_number,
                media_type=public_media_url[-3:],
                sent_by="system",
                message_content=msg_body,
                attachment_uid=letter_uid,
            )


def temp_save_memo_locally(file_bytes: bytes) -> str:
    if not os.path.exists("/tmp"):
        os.mkdir("/tmp")
    temp = "/tmp/audio.ogg"
    with open(temp, "wb") as f:
        f.write(file_bytes)
    return temp


def transcribe_voice_memo(uid: str) -> str:
    """Transcribes the voice memo with a uid already saved to the database

    Voice memos are saved to the database and their unique id is saved to the log table of messages. Their uid can then be used to access and transcribe the audio file. The function saves a pickle of the original whisper response as well as a pure text to the blob database and adds the text to the sql table of the message

    Args:
        uid (str): a 34 character string that is the unique identifier of each message in the database.

    Returns:
        str: The transcribed message of the audio file.
    """
    # check whether the message really is a audio file
    message_info = sql_client.get_message_by_uid(uid)
    assert (
        message_info["media_type"] == "audio"
    ), "Message is not an audio file but is attempted to be transcribed"

    # transcribe and save to disk. fp16 is not supported on the CPU version of the model. It is only supported on the GPU version.
    audio_bytes = blob_manager.get_audio_as_bytes(uid)
    # temporarily create a local file to feed into the whisper model
    transcript_text, duration = transcribe(audio_bytes)
    # Create a full text output and save
    # update the database entry to reflect which type of transcription has been applied
    sql_client.update_message_by_uid(
        uid,
        {
            "transcription_level": "API",
            "transcript": transcript_text,
            "memo_duration_secs": duration,
        },
    )

    return transcript_text


def summarise_text(
    input_text: str,
    phone_number: str,
    system_instructions: str = SYSTEM_INSTRUCTIONS,
    prompt: str = PROMPT,
) -> str:
    """summarises a text using the openai gpt4 API

    Args:
        input_text (str): the text that is supposed to be summarised
        phone_number (str): the phone number of the user that the summary is sent to
        prompt (str, optional): Prompt that tells GPT how to summarise the text. Defaults to PROMPT.
        store_and_send_result (bool, optional): Whether or not the summary should be saved to the database and sent to the user. Useful to set to false if you just want the summary. Defaults to True.

    Returns:
        str: Summary of the text
    """

    start = time.time()
    resp = openai.ChatCompletion.create(
        model=os.environ["GPT_MODEL"],
        messages=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": prompt + input_text},
        ],
        max_tokens=3000,
        temperature=0.2,
        stream=False,
    )
    print(f"API call took {time.time() - start} seconds.")

    summary = resp["choices"][0]["message"]["content"]

    # remove first word
    # get user_id
    user_id = sql_client.get_user_uid_from_phone(phone_number)
    letter_data = {
        "user_id": user_id,
        "cost_eur": None,
        "letter_input": input_text,
        "letter_content": summary,
        "prompt": prompt,
    }
    letter_uid = sql_client.add_letter(letter_data)
    letter_bytes = pdf_gen.create_letter_pdf_as_bytes(summary)
    blob_manager.save_letter(letter_bytes, letter_uid)
    public_url = blob_manager.set_letter_pdf_public(letter_uid)
    print(f"Public url for pdf: {public_url}")
    send_attachment(
        public_media_url=public_url,
        phone_number=phone_number,
        letter_uid=letter_uid,
    )
    send_message(
        msg="Here is a draft. You can make changes in the style of: 'hello doriss' -> 'Dear Doris' or just share instructions on how to change the text. Separate each command by a linebreak for best results.",
        phone_number=phone_number,
    )
    blob_manager.set_letter_pdf_private(letter_uid)

    return summary


def edit_letter_draft(edit_text: str, phone_number: str) -> str:
    # we need:
    # 1. original prompt
    # 2. original input text
    # 3. last edit
    # 4. Edit request
    last_letter_info = sql_client.get_users_last_letter_content(phone_number)
    input_text = last_letter_info["letter_input"]
    last_draft = last_letter_info["letter_content"]
    EDIT_PROMPT = "Please make the following changes to the previous text: \n\n"
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": PROMPT + input_text},
        {"role": "assistant", "content": last_draft},
        {"role": "user", "content": EDIT_PROMPT + edit_text},
    ]

    start = time.time()
    resp = openai.ChatCompletion.create(
        model=os.environ["GPT_MODEL"],
        messages=messages,
        max_tokens=4000,
        temperature=0.2,
        stream=False,
    )
    print(f"API call took {time.time() - start} seconds.")
    updated_content = resp["choices"][0]["message"]["content"]

    # store and send new draft
    user_id = sql_client.get_user_uid_from_phone(phone_number)
    letter_data = {
        "user_id": user_id,
        "letter_input": last_draft,
        "prompt": EDIT_PROMPT,
        "edit_text": edit_text,
        "letter_content": updated_content,
    }
    letter_uid = sql_client.add_letter(letter_data)
    letter_bytes = pdf_gen.create_letter_pdf_as_bytes(updated_content)
    blob_manager.save_letter(letter_bytes, letter_uid)
    public_url = blob_manager.set_letter_pdf_public(letter_uid)
    send_attachment(
        public_media_url=public_url,
        phone_number=phone_number,
        letter_uid=letter_uid,
    )
    send_message(
        msg="Here is the new draft. You can keep making more changes if you want to. When you're ready to send it just type '/send addressee_name'.",
        phone_number=phone_number,
    )
    blob_manager.set_letter_pdf_private(letter_uid)

    return updated_content


def process_voice_memo(uid: str, media_url: str) -> int:
    """Saves the voice memo to blob storage and then transcribes it

    Args:
        values (CombinedMultiDict): the values passed by the API post request arriving via twilio. It contains the information we need to retrieve the voice memo.
    """
    r = requests.get(media_url, allow_redirects=True, timeout=10)
    voice_memo_bytes = r.content
    blob_manager.save_voice_memo(voice_memo_bytes, uid)
    transcribe_voice_memo(uid)
    return 0
