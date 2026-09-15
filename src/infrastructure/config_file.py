#!/usr/bin/env python3
"""JSON configuration persistence."""

import json
import logging
import os

logger = logging.getLogger(__name__)


def read_config(config_file: str) -> dict:
    """Read JSON config file, return empty dict on error."""
    if not os.path.exists(config_file):
        return {}
    try:
        with open(config_file) as f:
            return json.load(f)
    except OSError as e:
        logger.warning("Could not read config file %s: %s", config_file, e)
        return {}
    except ValueError as e:
        logger.warning("Config file %s is not valid JSON: %s", config_file, e)
        return {}


def write_config(config_file: str, config: dict) -> bool:
    """Write JSON config file, return True on success."""
    try:
        config_dir = os.path.dirname(config_file)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(config, f)
        return True
    except OSError as e:
        logger.warning("Could not write config file %s: %s", config_file, e)
        return False
