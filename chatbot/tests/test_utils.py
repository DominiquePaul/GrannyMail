import pandas as pd
from grannymail.utils import get_message_spreadsheet, get_prompt_from_sheet


def test_get_message_spreadsheet():
    df = get_message_spreadsheet()
    assert isinstance(df, pd.DataFrame)
    assert all([x in df.columns for x in [
               "full_message_name", "Description", "version_main"]])


def test_get_prompt_from_sheet():
    prompt = get_prompt_from_sheet("help-success")
    assert isinstance(prompt, str)
    assert len(prompt) > 10
