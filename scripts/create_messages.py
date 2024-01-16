
from openai import OpenAI
from grannymail.utils import get_message_spreadsheet
import os
import sys
# add the 'grannymail' directory to the path
sys.path.append(os.path.join(sys.path[0], '../'))

# command = "add_address-error-too_short"
# command = "add_address-error-too_long"
# command = "add_address-error-msg_empty"
# command = "add_address_callback-success-follow_up"
# command = "add_address_callback-confirm"
# command = "add_address_callback-cancel"
# command = "delete_address-error-invalid_idx"

# command = "send-option-cancel_sending"
command = "send-option-confirm_sending"
# command = "help-success"


df = get_message_spreadsheet()
description = df[df["full_message_name"] == command]["Description"].values[0]
old_msg = df[df["full_message_name"] == command]["version_main"].values[0]


system = "You are a quirky, funny, sometimes rhyming assistant that makes suggestions for user messages in mobile apps in concise messages. You are a bit like Marvin from hitchikers guide to the galaxy"

prompt = """
You are creating user messages for a telegram/whatsapp bot that allows you to send voice messages to your loved ones and friends who are not tech-savvy. You can send a voice memo and the bot will convert it into a letter that you can send via physical mail right out of whatsapp/telegram.

Users can save contacts, record voice memos that are turned into drafts, edit these and finally send them as letters.

You are tasked to write a message for the bot that the user will receive. Don't greet the user. Be concise and clear. Be witty and funny. If the programme makes a mistake that might anger the user then try to reply in a way that they feel sympathy. Feel free to use emojis but not excessively.

The goal of the message is to make the user experience fun and easy. The most important thing is that the user understands what to do next and to avoid errors.

The briefing by our product manager for this message is:
{description}

Old message for inspiration (new message should be very different):
--------------------
Is this correct?
{old_msg}

New message:
--------------------
"""


openai_client = OpenAI()
completion = openai_client.chat.completions.create(
    model="gpt-3.5-turbo",
    temperature=1.3,
    messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": prompt.format(
            description=description, old_msg=old_msg)}
    ]
)

print(completion.choices[0].message.content)



# Feel free to make allusions to magic as if the service is magic itself.  Do not use the term "oopsie" or similar.
