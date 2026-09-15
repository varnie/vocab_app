"""Resolve the configured SQLite file location."""

import os

from config import DATA_DIR_KEY
from constants import CONFIG_FILE, DEFAULT_DB_PATH
from infrastructure.config_file import read_config


def get_db_path(config_file: str = CONFIG_FILE) -> str:
    """Determine DB path from config file or default."""
    config = read_config(config_file)
    custom_data_dir = config.get(DATA_DIR_KEY)

    if isinstance(custom_data_dir, str) and custom_data_dir.strip():
        custom_db_path = os.path.join(os.path.expanduser(custom_data_dir), "vocab.db")
        dir_path = os.path.dirname(custom_db_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        return custom_db_path

    return DEFAULT_DB_PATH
