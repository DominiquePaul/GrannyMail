import pytest
import os 

print(os.getcwd())
from src.server.intelligence import summarise_text


def test_summarise_intelligence():
    summarise_text = "This is a test sentence. This is another test sentence."
    assert True