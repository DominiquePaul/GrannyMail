
def get_message(msg_name: str) -> str:
    """Get a message from the messages database

    Args:
        msg_name (str): The name of the message to retrieve

    Returns:
        str: The message
    """
    with open(f"whatsgranny/messages/{msg_name}.txt", "r") as f:
        msg = f.read()
    return msg
