import io
import numpy as np
from openai import OpenAI
from rapidfuzz import fuzz

from grannymail.db_client import Address, User, SupabaseClient
from grannymail.utils import get_message, read_txt_file

openai_client = OpenAI()
db_client = SupabaseClient()


def is_message_empty(msg: str, remove_txt: str = "") -> bool:
    """Checks if a message is empty

    Args:
        msg (str): The message to check
        remove_txt (str): text known to be in the command that you want to remove

    Returns:
        bool: True if the message is empty, False otherwise
    """
    stripped_text = msg.replace(remove_txt, "").strip()
    is_empty = len(stripped_text) == 0
    return is_empty


def error_in_address(msg: str) -> str | None:
    # Strip to remove leading/trailing whitespace
    msg_lines = msg.strip().split("\n")
    # Is the message empty?
    if is_message_empty(msg):
        return get_message("add_addresss_msg_empty")
    if len(msg_lines) < 5:
        return get_message("add_address_msg_too_short")
    elif len(msg_lines) > 6:
        return get_message("add_address_msg_too_long")
    return None  # Explicitly return None for clarity

def strip_command(msg: str, command: str) -> str:
    """Strips a command from a message

    Args:
        msg (str): The message
        command (str): The command to strip

    Returns:
        str: The message with the command stripped
    """
    return msg.replace(command, "").strip()

def parse_new_address(msg: str) -> Address:
    """
    Parse a user message into an address object. The requirement is
    that the each item is separated by a newline.

    Args:
        msg (str): The user message

    Returns:
        Address: The parsed address
    """
    msg_lines = msg.strip("/add_address").strip().split("\n")
    if len(msg_lines) == 5:
        # No address line 2
        return Address(
            addressee=msg_lines[0],
            address_line1=msg_lines[1],
            address_line2=None,
            zip=msg_lines[2],
            city=msg_lines[3],
            country=msg_lines[4],
        )
    else:
        # Address line 2
        return Address(
            addressee=msg_lines[0],
            address_line1=msg_lines[1],
            address_line2=msg_lines[2],
            zip=msg_lines[3],
            city=msg_lines[4],
            country=msg_lines[5],
        )


def format_address_book(addresses: list[Address]) -> str:
    def format_single_message(address: Address) -> str:
        formatted_message = f"{address.addressee}\n" +\
            f"{address.address_line1}\n"

        if address.address_line2:
            formatted_message += f"{address.address_line2}\n"

        formatted_message += f"{address.zip} {address.city}\n" +\
            f"{address.country}"

        return formatted_message

    out = ""
    for idx, add in enumerate(addresses):
        out += f"\n{idx+1})\n{format_single_message(add)}\n"
    return out


def fetch_closest_address_index(fuzzy_string: str, address_book: list[Address]) -> int:
    """Returns the entry in the address book that is closest to the name supplied using fuzzy matching

    Args:
        fuzzy_string (str): search query term supplied by the user
        phone_number (str): phone number of the user whose address book should be searched

    Returns:
        str|dict: In case of an error a string with an error message is returned that can be passed on to the user. Otherwise a dictionary with the address details of the closest match is returned.
    """
    def serialise_address(address: Address) -> str:
        values = [address.addressee, address.address_line1,
                  address.address_line2, address.city, address.zip, address.country]
        values_subset = [x for x in values if x is not None]
        out = " ".join(values_subset)
        return out
    # get the closest match
    serialised_addresses = [serialise_address(ad) for ad in address_book]
    # get the closest match using the fuzzywuzzy package
    matching_scores = [fuzz.partial_ratio(fuzzy_string, ad)
                       for ad in serialised_addresses]
    return int(np.argmax(matching_scores))


def transcribe_voice_memo(voice_bytes: bytes) -> str:
    """Transcribes a voice memo

    Returns:
        str: The transcribed text
    """
    # Use an in-memory bytes buffer to avoid writing to disk
    buffer = io.BytesIO(voice_bytes)
    buffer.name = "temp_file.ogg"
    transcript = openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer
    )
    return transcript.text


def transcript_to_letter_text(transcript: str, user: User) -> str:
    """Converts a transcript to a letter text

    Args:
        transcript (str): The transcript

    Returns:
        str: The letter text
    """
    # get system prompt
    system_msg = read_txt_file("grannymail/prompts/system_prompt_de.txt")

    # get current prompt of user
    user = db_client.get_user(user)
    user_prompt = user.prompt
    if user_prompt is None:
        user_prompt = read_txt_file("grannymail/prompts/system_prompt_de.txt")
    final_prompt = f"Instructions:\n User input:\n{user_prompt}\nTranscript of the message: {transcript} Your letter:"

    # feed into gpt:
    completion = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": final_prompt}
        ]
    )
    return completion.choices[0].message.content
