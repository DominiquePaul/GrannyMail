import io
import typing as t

import numpy as np
from openai import AsyncOpenAI
from rapidfuzz import fuzz

from grannymail.db.classes import Address, User
from grannymail.db.supaclient import SupabaseClient
from grannymail.logger import logger

openai_client = AsyncOpenAI()
db_client = SupabaseClient()


class CharactersNotSupported(Exception):
    """Exception raised for characters not supported by the font."""

    def __init__(self, message="Characters not supported"):
        self.message = message
        super().__init__(self.message)


def strip_command(msg: str, command: str) -> str:
    """Strips a command from a message

    Args:
        msg (str): The message
        command (str): The command to strip

    Returns:
        str: The message with the command stripped
    """
    return msg.replace(command, "").strip()


def error_in_address(msg: str) -> str | None:
    # Strip to remove leading/trailing whitespace
    msg_lines = msg.strip().split("\n")
    if len(msg_lines) < 5:
        response = db_client.get_system_message("add_address-error-too_short")
        return response
    elif len(msg_lines) > 6:
        response = db_client.get_system_message("add_address-error-too_long")
        return response
    return None  # Explicitly return None for clarity


def parse_command(txt: str) -> tuple[str | None, str]:
    txt = txt.strip()
    txt = txt.replace("\n", " \n", 1)
    if txt.startswith("/"):
        command_end_idx = txt.find(" ")
        if command_end_idx == -1:  # Command only, no additional text
            return txt[1:], ""
        command = txt[1:command_end_idx]
        message_text = txt[command_end_idx:].strip()
        return command.lower(), message_text
    else:
        return "no_command", txt


def parse_new_address(msg: str) -> Address:
    """
    Parse a user message into an address object. The requirement is
    that the each item is separated by a newline.

    Args:
        msg (str): The user message

    Returns:
        Address: The parsed address
    """
    msg_lines = msg.replace("/add_address", "").strip().split("\n")
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
        formatted_message = f"{address.addressee}\n" + f"{address.address_line1}\n"

        if address.address_line2:
            formatted_message += f"{address.address_line2}\n"

        formatted_message += f"{address.zip} {address.city}\n" + f"{address.country}"

        return formatted_message

    address_list = []
    for idx, add in enumerate(addresses):
        address_list.append(f"\n{idx+1})\n{format_single_message(add)}\n")
    return "\n".join(address_list)


def fetch_closest_address_index(fuzzy_string: str, address_book: list[Address]) -> int:
    """Returns the entry in the address book that is closest to the name supplied using fuzzy matching

    Args:
        fuzzy_string (str): search query term supplied by the user
        phone_number (str): phone number of the user whose address book should be searched

    Returns:
        int: Returns the index of the closest match
    """

    def serialise_address(address: Address) -> str:
        values = [
            address.addressee,
            address.address_line1,
            address.address_line2,
            address.city,
            address.zip,
            address.country,
        ]
        values_subset = [x for x in values if x is not None]
        out = " ".join(values_subset)
        return out

    # get the closest match
    serialised_addresses = [serialise_address(ad) for ad in address_book]
    # get the closest match using the fuzzywuzzy package
    matching_scores = [
        fuzz.partial_ratio(fuzzy_string, ad) for ad in serialised_addresses
    ]
    if max(matching_scores) > 50:
        return int(np.argmax(matching_scores))
    else:
        return -1


async def transcribe_voice_memo(voice_bytes: bytes, duration: float) -> str:
    """Transcribes a voice memo asynchronously

    Returns:
        str: The transcribed text
    """
    # Use an in-memory bytes buffer to avoid writing to disk
    buffer = io.BytesIO(voice_bytes)
    buffer.name = "temp_file.ogg"
    transcript = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer,
        # response_format="text",
        # if duration takes unexpectedly long we don't want to deadlock the execution
        timeout=0.75 * duration,
    )
    logger.info(f"Transcribed text: {transcript.text}")
    return transcript.text


def check_supported_by_times_new_roman(s):
    """
    Checks if all characters in the string are likely to be supported by Times New Roman.
    This function checks against a broad approximation of character ranges known to be supported.

    Parameters:
    - s: A string to be checked.

    Raises:
        CharactersNotSupported: If the string contains characters not supported by Times New Roman
    """
    supported_ranges = [
        ("\u0020", "\u007E"),  # Basic ASCII
        ("\u00A0", "\u00FF"),  # Latin-1 Supplement
        ("\u0100", "\u017F"),  # Latin Extended-A
        ("\u0180", "\u024F"),  # Latin Extended-B (partial)
        ("\u0370", "\u03FF"),  # Greek and Coptic
        ("\u0400", "\u04FF"),  # Cyrillic
        # Add more ranges as needed
    ]

    s = s.replace("\n", "")
    unsupported_characters = set()

    for c in s:
        if not any(start <= c <= end for start, end in supported_ranges):
            unsupported_characters.add(c)

    if len(unsupported_characters) > 0:
        raise CharactersNotSupported(
            "Following characters are not supported: {unsupported_characters}"
        )


async def transcript_to_letter_text(transcript: str, user: User) -> str:
    """Converts a transcript to a letter text

    Args:
        transcript (str): The transcript

    Returns:
        str: The letter text
    """
    system_msg = db_client.get_system_message("system-prompt-letter_prompt")

    # get current prompt of user
    retrieved_user = db_client.get_user(user)
    optional_user_prompt = ""
    if retrieved_user.prompt:
        optional_user_prompt = "Additional user instructions: {retrieved_user.prompt}"

    final_prompt = f"Instructions: Turn the transcript below into a letter. Correct mistakes that my have arisen from a (faulty) transcription of the audio. \n\n {optional_user_prompt}\n\nTranscript of the message: \n{transcript} \n\nYour letter:\n"

    # feed into gpt:
    completion = await openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": final_prompt},
        ],
        # 5 tokens per second, assumed mean character length of 4 per token
        timeout=30,  # len(final_prompt)/(4*5),
    )
    transcript = completion.choices[0].message.content
    # check whether we only have latin letters
    check_supported_by_times_new_roman(transcript)

    return transcript  # type: ignore


async def implement_letter_edits(
    old_content: str,
    edit_instructions: str,
) -> str:
    """Implements the edits requested by the user

    Args:
        old_transcript (str): The lett
        edit_instructions (str): The edit instructions
        edit_prompt (str): The edit prompt

    Returns:
        str: The new transcript
    """
    edit_prompt = db_client.get_system_message("edit-prompt-implement_changes")
    system_message = db_client.get_system_message("edit-prompt-system_message")
    full_prompt = edit_prompt.format(old_content, edit_instructions)
    # feed into gpt:
    completion = await openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": full_prompt},
        ],
    )
    out: str = completion.choices[0].message.content  # type: ignore
    return out


def format_address_simple(address: Address) -> str:
    formatted_message = f"{address.addressee}\n" + f"{address.address_line1}\n"

    if address.address_line2:
        formatted_message += f"{address.address_line2}\n"

    formatted_message += f"{address.zip} {address.city}\n" + f"{address.country}"

    return formatted_message


def format_address_for_confirmation(address: Address) -> str:
    """Formats an address in a way that every item is clearly understood and can be confirmed by the user

    Args:
        address (Address): the address object to be formatted

    Returns:
        str: serialised address
    """
    formatted_message = (
        f"Addressee: {address.addressee}\n"
        + f"Address line 1: {address.address_line1}\n"
    )

    if address.address_line2:
        formatted_message += f"Address line 2: {address.address_line2}\n"

    formatted_message += (
        f"Postal Code: {address.zip} \nCity/Town: {address.city}\n"
        + f"Country: {address.country}"
    )

    return formatted_message
