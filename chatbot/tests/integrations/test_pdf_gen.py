import os
from uuid import uuid4

from pytest import fixture

from grannymail.domain.models import Address
from grannymail.integrations.pdf_gen import (
    create_and_save_letter,
    create_letter_pdf_as_bytes,
)


def test_create_letter_pdf_as_bytes(address, draft):
    bytes_resp = create_letter_pdf_as_bytes(draft.text, address)
    assert isinstance(bytes_resp, bytes)


def test_create_and_save_letter(address, draft):
    file_path = "./tests/test_data/dummy_letter_generation.pdf"
    if os.path.exists(file_path):
        os.remove(file_path)
    create_and_save_letter(file_path, draft.text, address)
    assert os.path.exists(file_path)


def test_multi_page_letter(address, draft):
    # has to be inspected manually
    text = draft.text * 100
    file_path = "./tests/test_data/test_generation_multi_page.pdf"
    if os.path.exists(file_path):
        os.remove(file_path)
    create_and_save_letter(file_path, text, address)
    assert os.path.exists(file_path)
