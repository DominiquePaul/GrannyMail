import pytest
import time

from grannymail.utils.message_utils import (
    implement_letter_edits,
    transcribe_voice_memo,
    transcript_to_letter_text,
)
from grannymail.utils.utils import get_prompt_from_sheet, read_txt_file


@pytest.mark.asyncio
async def test_transcribe_voice_memo():
    with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
        voice_bytes = f.read()
    duration = 10
    transcribed_text = await transcribe_voice_memo(voice_bytes, duration)
    assert isinstance(transcribed_text, str)
    assert len(transcribed_text) > 10


@pytest.mark.asyncio
async def test_transcript_to_letter_text(user):
    transcript = read_txt_file("tests/test_data/example_transcript.txt")
    user.prompt = "You rhyme every line"
    start = time.time()
    letter_content = await transcript_to_letter_text(transcript, user)
    duration = time.time() - start
    print(f"Time taken to create transcript: {duration}")
    assert isinstance(letter_content, str)


@pytest.mark.asyncio
async def test_implement_letter_edits():
    old_content = "Hallo Doris, mir geht es gut!"
    edit_instructions = "1) delete 'Doris' 2) replace 'gut' with 'schlecht'"
    edit_prompt = get_prompt_from_sheet("edit-prompt-implement_changes")
    response = await implement_letter_edits(old_content, edit_instructions, edit_prompt)
    assert isinstance(response, str)
    assert "schlecht" in response
    assert "Doris" not in response
    assert "gut" not in response
