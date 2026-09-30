"""Word of the Day word sources."""

import csv
import os
import random

from application.service_interfaces import WordSource


class LocalWordSource(WordSource):
    """Local word list source with CEFR-level words from CSV."""

    def __init__(self):
        self.words = self._load_words()

    def _load_words(self) -> dict[str, list[str]]:
        """Load words from CSV file (headword,CEFR)."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(base_path, "data", "ENGLISH_CERF_WORDS.csv")

        try:
            with open(csv_path, newline="") as f:
                reader = csv.DictReader(f)
                words: dict[str, list[str]] = {}
                for row in reader:
                    level = row.get("CEFR", "").upper()
                    word = row.get("headword", "").strip().lower()
                    if not level or not word:
                        continue
                    words.setdefault(level, [])
                    if word not in words[level]:
                        words[level].append(word)
                return words
        except (FileNotFoundError, KeyError, csv.Error):
            return {}

    def get_word(self, level: str) -> dict | None:
        """Get a random word for the given level."""
        level = level.upper()
        words = self.words.get(level, [])

        if not words:
            return None

        word = random.choice(words)  # ruff:ignore[suspicious-non-cryptographic-random-usage] - not cryptographic, just word selection
        return {"word": word, "level": level}
