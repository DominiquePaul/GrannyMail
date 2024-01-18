import time
from grannymail.utils.message_utils import transcribe_voice_memo, transcript_to_letter_text, implement_letter_edits
from grannymail.utils.utils import read_txt_file, get_prompt_from_sheet


def test_transcribe_voice_memo():
    with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
        voice_bytes = f.read()
    voice_bytes
    transcribed_text = transcribe_voice_memo(voice_bytes)
    assert isinstance(transcribed_text, str)
    assert len(transcribed_text) > 10


# def test_is_message_empty():
#     example = "/delete_address 1)"
#     assert is_message_empty(example) == False

#     example = "/delete_address"
#     assert is_message_empty(example) == False
#     assert is_message_empty(example, remove_txt="/delete_address") == True

#     example = "/delete_address   "
#     assert is_message_empty(example, remove_txt="/delete_address") == True


def test_transcript_to_letter_text(user):
    transcript = read_txt_file("tests/test_data/example_transcript.txt")
    user.prompt = "You rhyme every line"
    start = time.time()
    letter_content = transcript_to_letter_text(transcript, user)
    duration = time.time() - start
    print(f"Time taken to create transcript: {duration}")
    assert isinstance(letter_content, str)


def test_implement_letter_edits():
    old_content = "Hallo Doris, mir geht es gut!"
    edit_instructions = "1) delete 'Doris' 2) replace 'gut' with 'schlecht'"
    edit_prompt = get_prompt_from_sheet("edit-prompt-implement_changes")
    response = implement_letter_edits(
        old_content, edit_instructions, edit_prompt)
    assert isinstance(response, str)
    assert "schlecht" in response
    assert "Doris" not in response
    assert "gut" not in response
