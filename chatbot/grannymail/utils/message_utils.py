import io
import typing as t
from uuid import uuid4

import numpy as np
from openai import AsyncOpenAI
from rapidfuzz import fuzz

import grannymail.domain.models as m
from grannymail.logger import logger
from grannymail.services.unit_of_work import AbstractUnitOfWork

openai_client = AsyncOpenAI()

# General stuff


def strip_command(msg: str, command: str) -> str:
    """Strips a command from a message

    Args:
        msg (str): The message
        command (str): The command to strip

    Returns:
        str: The message with the command stripped
    """
    return msg.replace(command, "").strip()


def parse_command(txt: str) -> tuple[str | None, str]:
    txt = txt.strip()
    txt = txt.replace("\n", " \n", 1)
    if txt.startswith("/"):
        command_end_idx = txt.find(" ")
        if command_end_idx == -1:  # Command only, no additional text
            return txt[1:].lower(), ""
        command = txt[1:command_end_idx]
        message_text = txt[command_end_idx:].strip()
        return command.lower(), message_text
    else:
        return "_no_command", txt


# Address stuff


def error_in_address(msg: str, uow: AbstractUnitOfWork) -> str | None:
    # Strip to remove leading/trailing whitespace
    msg_lines = msg.strip().split("\n")
    if len(msg_lines) < 5:
        response = uow.system_messages.get_msg("add_address-error-too_short")
        return response
    elif len(msg_lines) > 6:
        response = uow.system_messages.get_msg("add_address-error-too_long")
        return response
    return None  # Explicitly return None for clarity


def parse_new_address(msg: str, created_at: str, user_id: str) -> m.Address:
    """
    Parse a user message into an address object. The requirement is
    that the each item is separated by a newline.

    Args:
        msg (str): The user message
        created_at (str): The timestamp of the message
        user_id (str): The user id

    Returns:
        Address: The parsed address
    """
    msg_lines = msg.replace("/add_address", "").strip().split("\n")
    if len(msg_lines) == 5:
        # No address line 2
        return m.Address(
            user_id=user_id,
            address_id=str(uuid4()),
            addressee=msg_lines[0],
            address_line1=msg_lines[1],
            address_line2=None,
            zip=msg_lines[2],
            city=msg_lines[3],
            country=msg_lines[4],
            created_at=created_at,
        )
    else:
        # Address line 2
        return m.Address(
            user_id=user_id,
            address_id=str(uuid4()),
            addressee=msg_lines[0],
            address_line1=msg_lines[1],
            address_line2=msg_lines[2],
            zip=msg_lines[3],
            city=msg_lines[4],
            country=msg_lines[5],
            created_at=created_at,
        )


def format_address_book(addresses: list[m.Address]) -> str:
    return "\n".join(
        [
            f"\n{idx+1})\n{add.format_address_as_string()}\n"
            for idx, add in enumerate(addresses)
        ]
    )


def fetch_closest_address_index(
    fuzzy_string: str, address_book: list[m.Address]
) -> int:
    """Returns the entry in the address book that is closest to the name supplied using fuzzy matching

    Args:
        fuzzy_string (str): search query term supplied by the user
        phone_number (str): phone number of the user whose address book should be searched

    Returns:
        int: Returns the index of the closest match
    """

    def serialise_address(address: m.Address) -> str:
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


# AI Stuff


class CharactersNotSupported(Exception):
    """Exception raised for characters not supported by the font."""

    def __init__(self, message="Characters not supported"):
        self.message = message
        super().__init__(self.message)


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


def _check_supported_by_times_new_roman(s):
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


async def transcript_to_letter_text(
    transcript: str, user_id: str, uow: AbstractUnitOfWork
) -> str:
    """Converts a transcript to a letter text

    Args:
        transcript (str): The transcript

    Returns:
        str: The letter text
    """
    system_msg = uow.system_messages.get_msg("system-prompt-letter_prompt")
    user = uow.users.get_one(user_id)
    optional_user_prompt = ""
    if user.prompt:
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
    assert completion.choices is not None
    assert completion.choices[0].message.content is not None
    transcript = completion.choices[0].message.content
    # check whether we only have latin letters
    _check_supported_by_times_new_roman(transcript)

    return transcript  # type: ignore


async def implement_letter_edits(
    old_content: str, edit_instructions: str, uow: AbstractUnitOfWork
) -> str:
    """Implements the edits requested by the user

    Args:
        old_transcript (str): The lett
        edit_instructions (str): The edit instructions
        edit_prompt (str): The edit prompt

    Returns:
        str: The new transcript
    """
    edit_prompt = uow.system_messages.get_msg("edit-prompt-implement_changes")
    system_message = uow.system_messages.get_msg("edit-prompt-system_message")
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
