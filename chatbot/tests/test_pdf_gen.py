import os

from pytest import fixture

from grannymail.domain.models import Address
from grannymail.integrations.pdf_gen import (
    create_and_save_letter,
    create_letter_pdf_as_bytes,
)


@fixture
def addressee_and_text():
    example_text_path = "./tests/test_data/example_letter_content.txt"
    example_text = read_txt_file(example_text_path)
    example_address = Address(
        addressee="Doris Paul",
        address_line1="Am Osterietweg 10",
        address_line2=None,
        zip="50996",
        city="Cologne",
        country="Germany",
    )
    return example_text, example_address


def test_create_letter_pdf_as_bytes(addressee_and_text):
    text, address = addressee_and_text
    bytes_resp = create_letter_pdf_as_bytes(text, address)
    assert isinstance(bytes_resp, bytes)


def test_create_and_save_letter(addressee_and_text):
    text, address = addressee_and_text
    file_path = "./tests/test_data/dummy_letter_generation.pdf"
    if os.path.exists(file_path):
        os.remove(file_path)
    create_and_save_letter(file_path, text, address)
    assert os.path.exists(file_path)


def test_multi_page_letter(addressee_and_text):
    # has to be inspected manually
    text, address = addressee_and_text
    text = text * 5
    file_path = "./tests/test_data/test_generation_multi_page.pdf"
    if os.path.exists(file_path):
        os.remove(file_path)
    create_and_save_letter(file_path, text, address)
    assert os.path.exists(file_path)
