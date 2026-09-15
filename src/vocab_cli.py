#!/usr/bin/env python3
"""CLI module for vocab app."""

import argparse
import sys

from bootstrap import create_vocab_service
from constants import CONFIG_FILE
from infrastructure.clipboard import get_clipboard_text
from infrastructure.current_phrase import clear_current_phrase, read_current_phrase, write_current_phrase
from infrastructure.notifications import send_notification


def run_cli():
    """Handle CLI actions (for desktop hotkeys)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="Save word from selection")
    parser.add_argument("--delete", action="store_true", help="Delete current word")
    parser.add_argument("--next", action="store_true", help="Show next word")
    args = parser.parse_args()

    if not (args.save or args.delete or args.next):
        return False

    vocab_service = create_vocab_service(CONFIG_FILE, must_exist=True)
    if not vocab_service:
        sys.exit(1)

    try:
        if args.save:
            try:
                result = get_clipboard_text()
                if not result:
                    send_notification("No text selected")
                    return False
                phrase = result.strip().lower()
                word = vocab_service.add_word(phrase, auto_translate=True)

                translation, trans_lang = vocab_service.get_translation_with_lang(word.id)
                if translation:
                    abbrev = vocab_service.get_language_abbreviation(trans_lang) if trans_lang else "—"
                    send_notification(f"<b>{phrase[:20]}</b> → {translation} [{abbrev}]")
                else:
                    send_notification(f"Word saved: {phrase[:30]}")

                write_current_phrase(phrase)
            except ValueError as e:
                send_notification(f"Invalid input: {e}")
            except Exception as e:
                send_notification(f"Error: {e}")

        if args.delete:
            phrase = read_current_phrase()
            if phrase:
                vocab_service.delete_word(phrase)
                send_notification(f"Word deleted: {phrase[:30]}")
                clear_current_phrase()

        if args.next:
            body = vocab_service.get_next_word_notification()
            if body:
                send_notification(body)

        return True
    finally:
        vocab_service.close()


if __name__ == "__main__":
    run_cli()
