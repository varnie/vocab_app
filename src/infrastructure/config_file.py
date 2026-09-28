#!/usr/bin/env python3
"""JSON configuration persistence."""

import json
import logging
import os
import tempfile

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
    temporary = None
    try:
        config_dir = os.path.dirname(config_file)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=config_dir or ".", delete=False) as f:
            temporary = f.name
            json.dump(config, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, config_file)
        return True
    except OSError as e:
        logger.warning("Could not write config file %s: %s", config_file, e)
        return False
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
