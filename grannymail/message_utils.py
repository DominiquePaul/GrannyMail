import numpy as np
from rapidfuzz import fuzz
from grannymail.db_client import Address
from grannymail.utils import get_message


def is_message_empty(msg: str) -> bool:
    """Checks if a message is empty

    Args:
        msg (str): The message to check

    Returns:
        bool: True if the message is empty, False otherwise
    """
    return len(msg.strip()) == 0


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
