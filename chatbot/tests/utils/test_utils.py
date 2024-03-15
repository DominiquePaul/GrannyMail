import pandas as pd

from grannymail.utils.utils import get_message_spreadsheet, get_prompt_from_sheet


def test_get_message_spreadsheet():
    df = get_message_spreadsheet()
    assert isinstance(df, pd.DataFrame)
    assert all([x in df.columns for x in ["message_identifier", "message_body"]])


def test_get_prompt_from_sheet():
    prompt = get_prompt_from_sheet("help-success")
    assert isinstance(prompt, str)
    assert len(prompt) > 10
