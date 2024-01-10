import typing as t
import pickle


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


def get_message(msg_name: str) -> str:
    """Get a message from the messages database

    Args:
        msg_name (str): The name of the message to retrieve

    Returns:
        str: The message
    """
    path = f"grannymail/messages/{msg_name}.txt"
    return read_txt_file(path)


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

