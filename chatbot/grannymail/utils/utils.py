import typing as t
from datetime import datetime, timedelta, timezone

import pandas as pd

import grannymail.config as cfg


def get_utc_timestamp(delta: t.Optional[timedelta] = None) -> str:
    now_utc = datetime.now(timezone.utc)
    if delta:
        now_utc += delta
    return now_utc.isoformat()


def get_message_spreadsheet() -> pd.DataFrame:
    # these are ok to be public.
    spreadsheet_key = "1FnY5mVvY48nvtMz8mi9rUq7gKLyJ-TpYc-ANAOwdu-0"
    sheet_name = "messages"

    # Construct the URL to retrieve data from Google Sheets
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_key}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    # Read the Google Spreadsheet into a Pandas DataFrame
    return pd.read_csv(url)


def get_prompt_from_sheet(
    prompt_name: str, version: str = cfg.MESSAGES_SHEET_NAME
) -> str:
    df = get_message_spreadsheet()
    df_subset = df[df["message_identifier"] == prompt_name][version]
    if df_subset.shape[0] == 0:
        raise ValueError(f"Could not find prompt {prompt_name} in spreadsheet")
    elif df_subset.shape[0] > 1:
        raise ValueError(
            f"Found multiple prompts with name {prompt_name} in spreadsheet"
        )
    return df_subset.iloc[0]
