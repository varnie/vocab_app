"""Isolated adapter for libraries that do not expose HTTP timeouts."""

import json
import sys


def main() -> None:
    provider, text, source, target = json.load(sys.stdin)
    if provider == "google_direct":
        import requests

        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
            timeout=(5, 10),
        )
        response.raise_for_status()
        data = response.json()
        result = "".join(item[0] for item in data[0] if item[0]) if data and data[0] else ""
    else:
        from deep_translator import GoogleTranslator, MyMemoryTranslator

        translator = GoogleTranslator if provider == "google_deep" else MyMemoryTranslator
        result = translator(source=source, target=target).translate(text)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
