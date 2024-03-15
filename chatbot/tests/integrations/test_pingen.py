from pytest import fixture

from grannymail.integrations.pingen import Pingen


@fixture
def pingen():
    pingen = Pingen()
    yield pingen


def test_send_letter(pingen):
    assert pingen.endpoint == "https://api-staging.pingen.com"
    file_path = "./tests/test_data/dummy_letter.pdf"
    with open(file_path, "rb") as f:
        file_as_bytes = f.read()
    upload_response = pingen.upload_and_send_letter(file_as_bytes, "test_file.pdf")
    assert len(upload_response["id"]) == 36
    assert isinstance(upload_response, dict)


def test_get_letter_details(pingen):
    assert pingen.endpoint == "https://api-staging.pingen.com"
    exant_uuid = "65012395-c251-425f-8acd-9a903e1ac267"
    re = pingen.get_letter_details(exant_uuid)
    assert isinstance(re, dict)
    assert re["id"] == exant_uuid
