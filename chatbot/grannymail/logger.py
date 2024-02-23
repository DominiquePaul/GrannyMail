import sys
import logging

# set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s (%(name)s - %(module)s - %(levelname)s): %(message)s"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
