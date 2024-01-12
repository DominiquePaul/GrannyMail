import time
from grannymail.message_utils import transcribe_voice_memo, is_message_empty, transcript_to_letter_text
from grannymail.utils import read_txt_file


def test_transcribe_voice_memo():
    with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
        voice_bytes = f.read()
    voice_bytes
    transcribed_text = transcribe_voice_memo(voice_bytes)
    assert isinstance(transcribed_text, str)
    assert len(transcribed_text) > 10


def test_is_message_empty():
    example = "/delete_address 1)"
    assert is_message_empty(example) == False

    example = "/delete_address"
    assert is_message_empty(example) == False
    assert is_message_empty(example, remove_txt="/delete_address") == True

    example = "/delete_address   "
    assert is_message_empty(example, remove_txt="/delete_address") == True



def test_transcript_to_letter_text(user):
    transcript = read_txt_file("tests/test_data/example_transcript.txt")
    user.prompt = "You rhyme every line"
    start = time.time()
    letter_content = transcript_to_letter_text(transcript, user)
    duration = time.time() - start
    print(f"Time taken to create transcript: {duration}")
    assert isinstance(letter_content, str)
