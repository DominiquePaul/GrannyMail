from whatsgranny.app.whisper_mod import transcribe
import whatsgranny.app.database_utils as dbu


def test_transcribe():
    blob_manager = dbu.BlobStorage()
    audio_bytes = blob_manager.get_audio_as_bytes("87d8047e-e997-4ae0-960a-e3f383d5726a")
    text, duration = transcribe(audio_bytes)
    assert isinstance(duration, float)
    assert duration > 0
    assert isinstance(text, str)
    assert len(text) > 0
