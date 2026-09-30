"""Pure time helpers shared across layers.

These are dependency-free so they can be imported from any layer
(domain, application, repositories, infrastructure) without violating
the dependency rule.
"""

from datetime import datetime, timezone


def utc_now_ts() -> int:
    """Current UTC time as epoch seconds."""
    return int(datetime.now(timezone.utc).timestamp())


def today_str() -> str:
    """Today's UTC date as 'YYYY-MM-DD' (matches WOTD history format)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def local_today_start_ts() -> int:
    """Local calendar midnight, while stored timestamps remain UTC epochs."""
    return int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
