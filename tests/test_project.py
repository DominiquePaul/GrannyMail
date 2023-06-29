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

def test_add_user(client):
    data = {"first_name": "Dominique Paul", "last_name": "Paul", "email": "dominique.c.a.paul@gmail.com", "phone_number": "4915159926162"}
    r = client.post("/add-user", data=data)
    assert r.status_code == 200


def test_help_message(client):
    r = client.post(
        "/message",
        data=DATA,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert (
        "These are the available commands: \n\n/summarise-last-memo: Summarises the last memo you sent\n\n/summarise-last-x-memos: Summarises the last x memos you sent. Needs to be followed by a number representing the number of memos you want to summarise\nExample: \n'/summarise-last-x-memos 4'\n\n/send: Sends the last letter content/summary to the addressee selected. Followed by the addressee's name. Input will be matched to the closest name in your address book.\nExample: \n'/send philipp hoesch'\n\n/confirm: Needs to be sent after '/send' as a final confirmation to send the letter\n\n/show-address-book: Shows all addressees you have saved\n\n/new-addressee: Adds a new addressee to your address book. Followed by address in the following format, details separated by line breaks: 'name, address line 1, address line 2 (optonal), post code, city, country'.\nExample: \n'/new-addressee Philipp Hoesch\nExample company\nKarlstrasse 1\n80333\nMunich\nGerman"
        in r.text
    )


# tests that a voice memo is sent to the app. It should be transcribed and the text should be sent back to the user
def test_voice_memo_sent(client):
    payload = DATA.copy()
    payload["MediaContentType0"] = "audio/ogg"
    payload["Body"] = ""
    payload["MediaUrl0"] = "https://api.twilio.com/2010-04-01/Accounts/ACfd0053bf7324c8ddfb030bd8ba62b0ef/Messages/MM82a19e0cfcc7a835b35be4ffa0bc79f3/Media/MEdd359c54910c94a91966bca2058a289b"
    payload["NumMedia"] = 1
    r = client.post(
        "/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200

def get_address_book(client):
    payload = DATA.copy()
    payload["Body"] = "/show-address-book"
    r = client.post(
        "/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return r


def test_add_entry_to_address_book(client):
    r = get_address_book(client)
    assert "Dominique Paul" not in r.text, "Dominique Paul already in address book. Test cannot work."

    address = """/new-addressee
Dominique Paul
C/O Heuer
Wolliner strasse 2
10435
Berlin
Germany"""
    data = DATA.copy()
    data["Body"] = address
    r = client.post(
        "/message",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert "We recorded the following address:" in r.text

    # confirm address
    data["Body"] = "/confirm-address"
    r = client.post(
        "/message",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200

    # now show address book again
    r = get_address_book(client)
    assert "Dominique Paul" in r.text, "Dominique Paul was not added to the address book"
    assert r.status_code == 200


def test_negative_add_entry_to_address_book(client):
    pass


def test_summarise_last_memo(client):
    payload = DATA.copy()
    payload["Body"] = "/summarise-last-memo"
    r = client.post(
        "/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200


def test_edit_letter(client):
    payload = DATA.copy()
    payload["Body"] = "/edit 'Liebe Omi Doris' -> 'Liebe Doris' \n 'Ich wollte Dir von meiner aufregenden Woche erzählen' -> ''"
    r = client.post("/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200


def test_edit_letter2(client):
    payload = DATA.copy()
    payload["Body"] = "/edit 'Anna Örtha' -> 'Anna Oerther'"
    r = client.post("/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200



def test_send_letter(client):
    payload = DATA.copy()
    payload["Body"] = "/send Dominique Paul"
    r = client.post("/message",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert "If this is correct, please confirm sending this out" in r.text
