import os

from logging import FileHandler, Logger, getLogger


def get_logger() -> Logger:
    """
    Get the Uvicorn logger and configure it based on environment variables.

    Returns:
        Logger: Configured Uvicorn logger.
    """

    logger = getLogger("uvicorn")

    if os.environ.get("LOG_LEVEL"):
        logger.setLevel(os.environ["LOG_LEVEL"])

    if os.environ.get("LOG_FILE"):
        file_handler = FileHandler(os.environ["LOG_FILE"])
        logger.addHandler(file_handler)

    if os.environ.get("DEBUG"):
        logger.setLevel("DEBUG")

    return logger
