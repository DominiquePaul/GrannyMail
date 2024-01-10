from grannymail.message_utils import transcribe_voice_memo


def test_transcribe_voice_memo():
    with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
        voice_bytes = f.read()
    transcribed_text = transcribe_voice_memo(voice_bytes)
    assert isinstance(transcribed_text, str)
    assert len(transcribed_text) > 10
