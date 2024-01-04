from whatsgranny.utils import get_message


def test_get_message():
    msg = get_message('help_welcome_message')
    assert msg == """Welcome to GrannyMail

📣 → 🤖 → 💌 → 📬 → 👵🏻 → 🥰

Send me a voice message and I will turn it into a letter that you can send to your Grandma, Grandpa or anyone else. All without leaving Telegram!

Already have an account and added your telegram ID? 
Start by sending me a voicememo. 🗣️

No account yet?
Set one up and learn more at www.grannymail.io 🤳🏻"""
