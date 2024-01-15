import typing as t
import pickle
import pandas as pd


def save_pickle(obj: t.Any, file_loc: str) -> None:
    """Saves any python object as a pickle file for fast and simple saving

    Args:
        obj (Any): the python object that you want to save
        file_loc (str): file location of the object
    """
    with open(file_loc, "wb") as handle:
        pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(file_loc: str) -> t.Any:
    """Load any pickle object from disk into memory

    Args:
        file_loc (str): path of pickle file to load

    Returns:
        Any: returns the python object that was stored as a pickle
    """
    with open(file_loc, "rb") as handle:
        obj = pickle.load(handle)  # nosec: B301
        return obj


# def get_message(msg_name: str) -> str:
#     """Get a message from the messages database

#     Args:
#         msg_name (str): The name of the message to retrieve

#     Returns:
#         str: The message
#     """
#     path = f"grannymail/messages/{msg_name}.txt"
#     return read_txt_file(path)


def read_txt_file(path) -> str:
    """Reads a text file from disk

    Args:
        path (str): path to the text file

    Returns:
        str: contents of the text file
    """
    with open(path, "r") as f:
        text = f.read()
    return text


def get_message_spreadsheet() -> pd.DataFrame:
    # these are ok to be public.
    spreadsheet_key = '1FnY5mVvY48nvtMz8mi9rUq7gKLyJ-TpYc-ANAOwdu-0'
    sheet_name = 'messages'

    # Construct the URL to retrieve data from Google Sheets
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_key}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    # Read the Google Spreadsheet into a Pandas DataFrame
    return pd.read_csv(url)


def get_prompt_from_sheet(prompt_name: str, version: str = "version_main") -> str:
    df = get_message_spreadsheet()
    df_subset = df[df["full_message_name"] == prompt_name][version]
    if df_subset.shape[0] == 0:
        raise ValueError(f"Could not find prompt {prompt_name} in spreadsheet")
    elif df_subset.shape[0] > 1:
        raise ValueError(
            f"Found multiple prompts with name {prompt_name} in spreadsheet")
    return df_subset.iloc[0]

# def get_messages_as_dict(column_name="version_main"):
#     df = get_message_spreadsheet()
#     return df.set_index('full_message_name')[column_name].to_dict()
