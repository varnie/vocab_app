"""CSV output adapter for vocabulary exports."""

import csv

from domain.entities import Word


def write_vocabulary_csv(filepath: str, words: list[Word], source_lang: str) -> None:
    """Write vocabulary rows with the public CSV column layout."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "source language", "target language"])
        for word in words:
            writer.writerow(
                [
                    word.phrase,
                    word.translation,
                    source_lang,
                    word.language_code,
                ]
            )
