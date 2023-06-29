import os
import typing as t
import shutil
import openai
from pydub import AudioSegment
import whatsgranny.app.database_utils as dbu


# # the whisper model that will transcribe the voice memo. Options are [tiny, base, small, medium,
# MODEL_SIZE = os.environ["MODEL_SIZE"]
# MODEL = whisper.load_model(MODEL_SIZE, download_root="whisper_models")
openai.api_key = os.environ["OPENAI_KEY"]


# Note: you need to be using OpenAI Python v0.27.0 for the code below to work


def temp_save_memo_locally(file_bytes: bytes) -> str:
    if not os.path.exists("./tmp"):
        os.mkdir("./tmp")
    path_tmp = "./tmp/audio.ogg"
    with open(path_tmp, "wb") as f:
        f.write(file_bytes)
    return path_tmp


def file_to_whisper(path: str):  # -> whisper.Whisper:
    """Returns the text from a url"""
    audio_file = open("/path/to/file/audio.mp3", "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript


def whisper_to_text(whisper_obj) -> str:
    """Returns the text from a whisper object"""
    return whisper_obj.text


def transcribe(audio_bytes: bytes) -> t.Tuple[str, float]:
    """Returns the text from a url"""
    path_tmp_ogg = temp_save_memo_locally(audio_bytes)
    path_tmp_mp3 = path_tmp_ogg.replace(".ogg", ".mp3")
    audio_file = AudioSegment.from_file(path_tmp_ogg, format="ogg")
    audio_file.export(path_tmp_mp3, format="mp3")
    with open(path_tmp_mp3, "rb") as f:
        transcript = openai.Audio.transcribe("whisper-1", f)
    shutil.rmtree("./tmp")
    return transcript["text"], audio_file.duration_seconds


if __name__ == "__main__":
    blob_manager = dbu.BlobStorage()
    audio_bytes = blob_manager.get_audio_as_bytes(
        "08d5cc64-c9a2-4c31-a2d3-2c8ee384df42"
    )
    tmp_path = temp_save_memo_locally(audio_bytes)
    whisper_obj = file_to_whisper(tmp_path)
    text = whisper_to_text(whisper_obj)
