import os
import re
import time

from werkzeug.datastructures import CombinedMultiDict
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import redis
from rq import Queue
from rapidfuzz import fuzz
import numpy as np

import intelligence
import database_utils as dbu
from pingen import Pingen
from pdf_gen import create_letter_pdf_as_bytes

r = redis.from_url(os.environ["REDIS_URL"])
assert r.ping(), "No connection to Redis"
REDIS_QUEUE = Queue(connection=r, default_timeout=3600)

load_dotenv()

blob_manager = dbu.BlobStorage()
sql_client = dbu.Supabase_sql_client()
pingen_manager = Pingen()

app = Flask(__name__)

COMMANDS = {
    "/summarise-last-memo": {
        "description": "Summarises the last memo you sent",
        "example_input": None,
    },  # Will send summary and an indication that user needs to select where to send it to from addressee list
    "/summarise-last-x-memos": {
        "description": "Summarises the last x memos you sent. Needs to be followed by a number representing the number of memos you want to summarise",
        "example_input": "4",
    },  # requires integer -> response is same as above
    "/send": {
        "description": "Sends the last letter content/summary to the addressee selected. Followed by the addressee's name. Input will be matched to the closest name in your address book.",
        "example_input": "philipp hoesch",
    },  # requires addressee id  -> Returns a message with the summary and the address
    "/confirm": {
        "description": "Needs to be sent after '/send' as a final confirmation to send the letter",
        "example_input": None,
    },  # no input -> Will send the summary to the address
    "/show-address-book": {
        "description": "Shows all addressees you have saved",
        "example_input": None,
    },  # no input -> Will send the address book of the user
    "/new-addressee": {
        "description": "Adds a new addressee to your address book. Followed by address in the following format, details separated by line breaks: 'name, address line 1, address line 2 (optonal), post code, city, country'.",
        "example_input": "Philipp Hoesch\nExample company\nKarlstrasse 1\n80333\nMunich\nGermany",
    },  #
    "/confirm-address": {
        "description": "Confirms whether the details of your last addressee are correct. Can only be used if last message was /new-addressee.",
        "example_input": None,
    },  # No input -> Will confirm the previous address.
    "/help": {
        "description": "Shows and explains all commands.",
        "example_input": None,
    },  # Lists all commands
    "/edit": {
        "description": "Edit the last letter draft. Separate commands with a new line for highest effectiveness",
        "example_input": "'hellp doriss' -> 'hello Doris'\n'make the tone more casual'.",
    },  # Lists all commands
}


def send_all_addressees(phone_number: str) -> str:
    """Returns the address book of a user

    Args:
        phone_number (str): phone number of the user. Used to retrieve address book from database

    Returns:
        str: XML formatted message that can be sent to the user
    """
    # Get all addressees associated with users phone number from database
    addressees = sql_client.get_users_address_book(phone_number)
    if len(addressees) == 0:
        return create_response(
            "You don't have any addressees yet. You can create one by sending '/new-addressee'.",
            phone_number,
        )
    else:
        # format for one address
        add_template = "*Address {idx}:* \n{addressee_name}\n{address_line1}\n{address_line2}{post_code} {city}\n{country}\n\n\n"
        # Convert list of dicts of addressees into readble format for message
        message = "These are your addressees:\n\n"
        for idx, addressee in enumerate(addressees):
            addressee["address_line2"] = (
                addressee["address_line2"] + "\n" if addressee["address_line2"] else ""
            )
            message += add_template.format(idx=idx + 1, **addressee)
        # Send message to user
        return create_response(message, phone_number)


def create_response(message: str, phone_number: str | None = None) -> str:
    """Turns a string into a string formatted as a xml response for Twilio

    Args:
        message (str): The text message that should be sent
        phone_number (str|None, optional): The phone number of the user. If passed then the reponse is logged to the database. Defaults to None which means that the response is not logged.

    Returns:
        str: A string formatted as a XML message that Twilio requires to respond to a message
    """
    assert (
        len(message) <= 1600
    ), f"Message is too long. Max length is 1600 characters. Your message has {len(message)} characters."
    if isinstance(phone_number, str):
        sql_client.add_message(
            sent_by="system",
            phone_number=phone_number,
            media_type="text",
            message_content=message,
        )
    elif phone_number is not None:
        raise TypeError(
            "Phone number must be a string if it is provided and is not None."
        )
    response = MessagingResponse()
    response.message(message)
    return str(response)


def get_message_type(values: CombinedMultiDict) -> str:
    """Checks whether the message is a text or audio message

    This informs the app how to process the message

    Args:
        values (CombinedMultiDict): the raw request sent in the API request

    Returns:
        str: either returns "text" or "audio"
    """
    if values["NumMedia"] != "0":
        if request.values["MediaContentType0"] == "audio/ogg":
            return "audio"
    elif values.get("Body", None) is not None:
        return "text"
    raise AssertionError("Unknown media type")


def summarise_last_n_memos(values: CombinedMultiDict, n_memos: int) -> str:
    """Fetches last n memos from database and triggers summarisation

    Args:
        values (CombinedMultiDict): _description_
        n_memos (int): _description_
    """
    # get data for the last memos from data
    memos = sql_client.get_last_x_memos(values["WaId"], n_memos)
    response = ""
    if len(memos) == 0:
        # Inform user that they need to send memos first
        return create_response(
            "You have not sent any voice memos yet. Please send a voice memo to get started.",
            values["WaId"],
        )
    elif len(memos) < n_memos:
        response += (
            f"You have so far only sent {len(memos)} so far. Summarising these instead."
        )
        n_memos = len(memos)
    # check that all memos have been transcribed
    for i, memo in enumerate(memos):
        assert (
            memo["transcription_level"] is not None
        ), f"Not all memos have been transcribed (memo {i} failed)."
    # concatenate memos to one message for summarisation by LLM
    summarisation_input = "\n\n".join([memo["transcript"] for memo in memos])
    # Trigger summarisation
    job = REDIS_QUEUE.enqueue(
        intelligence.summarise_text, args=[summarisation_input, values["WaId"]]
    )
    print(f"Started job {job.get_id()}")
    # intelligence.summarise_text(summarisation_input, values["WaId"])
    response += "Your summary is being prepared. We will send it you for editing once its ready \U0001F916"
    return create_response(response, values["WaId"])


def parse_out_command(msg: str, return_as_lines: bool) -> str | list:
    """Parses a message into all relevant lines but excludes the command and resulting empty lines

    This is very useful for extracting the content of a message after the command and especially useful if the message is a list of items. This is the case for the address or for edits made to a letter draft.

    Args:
        msg (str): The original text message of the user
        return_as_lines (bool): Whether to return the message as a list of lines or as a single string (original message without command)

    Returns:
        list: A list of all lines in the message that are not empty and do not contain a command
    """
    # split message into lines
    msg_lines = msg.split("\n")
    msg_lines[0] = re.sub(r"\/\w+[-\w]+", "", msg_lines[0])
    # edit lines to remove leading and trailing whitespace
    msg_lines = [line.strip() for line in msg_lines]
    # remove any words in a list item starting with a '/'
    msg_lines = [line.split("/")[0].strip() for line in msg_lines]
    msg_lines = [line for line in msg_lines if line != ""]
    if return_as_lines:
        return msg_lines
    else:
        return "\n".join(msg_lines)


def parse_address_message(msg: str) -> str | dict:
    """Takes a message and parses it into a dictionary of address details

    Args:
        msg (str): The original text message of the user

    Returns:
        str|dict: If the message could not be parsed a string with an error message is returned. Otherwise a dictionary with the address details is returned.
    """
    print(msg)
    msg_lines = parse_out_command(msg, return_as_lines=True)
    # check that we have at least 5 lines
    if len(msg_lines) < 5:
        return "Please provide at least 5 lines in your address message. Remember to include a line break between each entry. You can use this example as a reference: '/new-addressee Philipp Hoesch\nExample company\nKarlstrasse 1\n80333  \nMunich \n Germany'"
    elif len(msg_lines) > 6:
        return "Your address should not contain more than 6 lines (excluding the command). You can use this example as a reference:\n\n'/new-addressee\n Philipp Hoesch\nExample company\nKarlstrasse 1\n80333  \nMunich \n Germany'"
    elif len(msg_lines) == 5:
        return {
            "addressee_name": msg_lines[0],
            "address_line1": msg_lines[1],
            "address_line2": None,
            "post_code": msg_lines[2],
            "city": msg_lines[3],
            "country": msg_lines[4],
        }
    else:
        return {
            "addressee_name": msg_lines[0],
            "address_line1": msg_lines[1],
            "address_line2": msg_lines[2],
            "post_code": msg_lines[3],
            "city": msg_lines[4],
            "country": msg_lines[5],
        }


def fetch_closest_addressee_match(fuzzy_string: str, phone_number: str) -> str | dict:
    """Returns the entry in the address book that is closest to the name supplied using fuzzy matching

    Args:
        fuzzy_string (str): search query term supplied by the user
        phone_number (str): phone number of the user whose address book should be searched

    Returns:
        str|dict: In case of an error a string with an error message is returned that can be passed on to the user. Otherwise a dictionary with the address details of the closest match is returned.
    """
    addressees = sql_client.get_users_address_book(phone_number)
    if len(addressees) == 0:
        return "You have not added any addressees yet. You can use the '/new-addressee' command to add a new addressee."
    # get the closest match
    names = [addressee["addressee_name"] for addressee in addressees]
    # get the closest match using the fuzzywuzzy package
    matching_scores = [fuzz.ratio(fuzzy_string, name) for name in names]
    argmax_idx = np.argmax(matching_scores)
    return addressees[argmax_idx]


def send_letter(address_uid, letter_content_uid) -> None:
    pass


@app.route("/message", methods=["POST"])
def process_message():
    start = time.time()
    msg_type = get_message_type(request.values)
    msg = request.values.get("Body", None)
    # log message to database
    uid = sql_client.add_message(
        sent_by="user",
        phone_number=request.values["WaId"],
        media_type=msg_type,
        message_content=msg,
        message_sid=request.values["MessageSid"],
    )
    if msg_type == "audio":
        job = REDIS_QUEUE.enqueue(
            intelligence.process_voice_memo, args=[uid, request.values["MediaUrl0"]]
        )
        print(f"Started job {job.id}")
        return create_response(f"Processing message... \U0001F916")
    elif msg_type == "text":
        # check if the message starts with one of the official commands
        first_word = msg.split(" ")[0].lower()
        if first_word in COMMANDS.keys():
            if first_word == "/summarise-last-memo":
                return summarise_last_n_memos(request.values, 1)
            elif first_word == "/summarise-last-x-memos":
                # TODO: add a check if a number was passed else reply with a hint to improve and tell the user what went wrong
                n_memos = int(msg.split(" ")[1])
                return summarise_last_n_memos(request.values, n_memos)

            elif first_word == "/edit":
                # extract text from message
                message = parse_out_command(msg, return_as_lines=False)
                intelligence.edit_letter_draft(
                    edit_text=message, phone_number=request.values["WaId"]
                )

            elif first_word == "/send":
                # Identify recipient
                addressee = msg.split(" ")
                if len(addressee) <= 1:
                    return create_response(
                        "Please specify the name of who you want to sedn the summary to."
                    )
                addressee = " ".join(addressee[1:])
                closest_addressee_or_error = fetch_closest_addressee_match(
                    addressee, request.values["WaId"]
                )
                if isinstance(closest_addressee_or_error, str):
                    return create_response(
                        "Error retreiving address: " + closest_addressee_or_error
                    )
                else:
                    ### Create
                    # fetch latest content
                    last_letter = sql_client.get_last_user_letter_content(
                        request.values["WaId"]
                    )
                    last_letter_uid = last_letter["uid"]
                    last_letter_content = last_letter["content"]
                    # create pdf
                    letter_bytes = create_letter_pdf_as_bytes(
                        input_text=last_letter_content,
                        address=closest_addressee_or_error,
                    )
                    # save pdf to blob
                    blob_manager.save_letter(letter_bytes, last_letter_uid)
                    # update sql to reflect that a pdf does exist in blob storage
                    sql_client.update_letter_content(
                        last_letter_uid, update_vals={"pdf_created": True}
                    )

                    ### Send back the pdf file to user
                    # briefly make the pdf file accessible so that twilio can send it to the user
                    pdf_url = blob_manager.set_letter_pdf_public(last_letter_uid)

                    # send the pdf file to the user
                    intelligence.send_attachment(
                        pdf_url, request.values["WaID"], last_letter_uid
                    )

                    # make the file private again
                    blob_manager.set_letter_pdf_private(last_letter_uid)

                    # send message to user with instructions for next steps
                    msg = "If this is correct, please confirm sending this out by typing '/confirm' to send the message. If the address didn't match then try sending '/send' again. You can view your address book by sending '/show-address-book'."
                    return create_response(msg)
            elif first_word == "/confirm":
                # Requires the last message to have been '/send'
                last_message = sql_client.get_last_nth_user_message(
                    phone_number=request.values["WaId"], n=1
                )
                if last_message.sep(" ")[0] != "/send":
                    return create_response(
                        "Nothing to confirm. Last message needs to have been '/send'"
                    )
                else:
                    # send the last summary as a letter to the addressee
                    # get the last letter as bytes
                    last_letter = sql_client.get_last_user_letter_content(
                        request.values["WaId"]
                    )
                    last_letter_uid = last_letter["uid"]
                    letter_as_bytes = blob_manager.get_letter_as_bytes(last_letter_uid)
                    pingen_letter_uid = pingen_manager.upload_and_send_letter(
                        file_as_bytes=letter_as_bytes
                    )
                    return create_response("Letter has been sent.")
            elif first_word == "/show-address-book":
                return send_all_addressees(request.values["WaId"])
            elif first_word == "/new-addressee":
                parsed_address_or_error = parse_address_message(msg)
                if isinstance(parsed_address_or_error, str):
                    # a string with an error is retured if the message could not be parsed. Otherwise a dictionary with the address details is returned.
                    return create_response(
                        f"Your address could not be parsed: {parsed_address_or_error}. Please try again."
                    )
                # send message back to check if the address is correct
                msg = "We recorded the following address: \n\n"
                for key, value in parsed_address_or_error.items():
                    msg += f"{key}: {value}\n"
                msg += "\n\nIf this address is correct, then please confirm it by sending '/confirm-address'."
                return create_response(msg, request.values["WaId"])
            elif first_word == "/confirm-address":
                # check whether last message was an attempt to add an address
                last_message = sql_client.get_last_nth_user_message(
                    phone_number=request.values["WaId"], n=2
                )
                last_message = last_message["message_content"]
                if last_message.split(" ")[0] != "/new-addressee":
                    return create_response(
                        "Last message was not an attempt to add an addressee. Add a new address with '/new-addressee'"
                    )
                # add address from last message to database
                parsed_address = parse_address_message(last_message)
                sql_client.add_address_to_user_addressbook(
                    request.values["WaId"], parsed_address
                )
                return create_response(
                    "Address added to address book. You can view all your addressees with '/show-address-book'"
                )
            elif first_word == "/help":
                # Create help message
                msg = "These are the available commands: \n\n"
                for command in COMMANDS.keys():
                    msg += f"{command}: {COMMANDS[command]['description']}\n"
                    if COMMANDS[command]["example_input"] is not None:
                        msg += (
                            "Example: \n'"
                            + command
                            + " "
                            + COMMANDS[command]["example_input"]
                            + "'\n"
                        )
                    msg += "\n"
                # return create_response("test", request.values["WaId"])
                print(time.time() - start)
                return create_response(msg, request.values["WaId"])
            else:
                msg = f"Sorry, I don't understand '{msg}'. You can view all commands using '/help'."
                return create_response(msg, request.values["WaId"])
        else:
            return create_response(
                f"Hi, I am your GrannyBot. Record a voice memo as if you were speaking to your grandma. It will be transcribed so you can see whether the transcription worked. Once you would like to create a letter you can tell me to summarise the last x memos and draft a letter using '/summarise-last-memo' or '/summarise-last-x-memos _number_'. You can also view all commands using '/help'.",
                request.values["WaId"],
            )


@app.route("/send_transcript/<uid>")
def send_transcript(uid: str):
    """Send a message with the transcript to the user once transcription has completed.

    This endpoint is triggered by the background task

    Args:
        uid (str): unique identifier of the message that was transcribed
    """
    # get the transcript from the database
    message_info = sql_client.get_message_by_uid(uid)
    # send the transcript to the user
    message = (
        "Your voice memo has been transcribed. Here is what you said: \n\n"
        + message_info["text"]
        + "\n\n (remember that it does not have to be perfect for the summary to work)"
    )
    intelligence.send_message(message, message_info["phone_number"])


if __name__ == "__main__":
    print("ready to go...")
    app.run()
