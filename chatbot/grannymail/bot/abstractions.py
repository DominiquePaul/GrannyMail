from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Union

# class MessagingPlatform(ABC):

# @abstractmethod
# def send_message(self, recipient_id: str, message: str) -> Any:
#     """
#     Send a text message to a recipient.

#     :param recipient_id: The unique identifier for the recipient.
#     :param message: The message text to be sent.
#     :return: Implementation specific response.
#     """
#     pass

# @abstractmethod
# def send_file(self, recipient_id: str, file_bytes: bytes, file_name: str, mime_type: str) -> Any:
#     """
#     Send a file to a recipient.

#     :param recipient_id: The unique identifier for the recipient.
#     :param file_bytes: The bytes of the file to be sent.
#     :param file_name: The name of the file.
#     :param mime_type: The MIME type of the file.
#     :return: Implementation specific response.
#     """
#     pass
