DATA = {
    "MediaContentType0": "text",
    "Body": "/help",
    "SmsMessageSid": "MM82a19e0cfcc7a835b35be4ffa0bc79f3",
    "NumMedia": "0",
    "SmsSid": "MM82a19e0cfcc7a835b35be4ffa0bc79f3",
    "WaId": "4915159926162",
    "SmsStatus": "received",
    "To": "whatsapp:+14155238886",
    "NumSegments": "1",
    "ReferralNumMedia": "0",
    "MessageSid": "MM82a19e0cfcc7a835b35be4ffa0bc79f3",
    "AccountSid": "ACfd0053bf7324c8ddfb030bd8ba62b0ef",
    "From": "whatsapp:+4915159926162",
    "MediaUrl0": "",
    "ApiVersion": "2010-04-01",
}


def test_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "Hello, World!"


def test_help_message(client):
    r = client.post(
        "/message",
        data=DATA,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>These are the available commands: \n\n/summarise-last-memo: Summarises the last memo you sent\n\n/summarise-last-x-memos: Summarises the last x memos you sent. Needs to be followed by a number representing the number of memos you want to summarise\nExample: \n'/summarise-last-x-memos 4'\n\n/send: Sends the last letter content/summary to the addressee selected. Followed by the addressee's name. Input will be matched to the closest name in your address book.\nExample: \n'/send philipp hoesch'\n\n/confirm: Needs to be sent after '/send' as a final confirmation to send the letter\n\n/show-address-book: Shows all addressees you have saved\n\n/new-addressee: Adds a new addressee to your address book. Followed by address in the following format, details separated by line breaks: 'name, address line 1, address line 2 (optonal), post code, city, country'.\nExample: \n'/new-addressee Philipp Hoesch\nExample company\nKarlstrasse 1\n80333\nMunich\nGerman..."
        in r.text
    )


# tests that a voice memo is sent to the app. It should be transcribed and the text should be sent back to the user
def test_voice_memo_sent(client):
    pass


# tests the case that a user requests her address book
def test_get_address_book(client):
    pass


def test_add_entry_to_address_book(client):
    address = """/new-addressee
Philipp Hoesch
Example company
Karlstrasse 1
80333
Munich
Germany"""
    data = DATA.copy()
    data["Body"] = address
    r = client.post(
        "/message",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_negative_add_entry_to_address_book(client):
    pass


def test_summarise_last_memo(client):
    pass


def test_send_letter(client):
    pass