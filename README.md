# Vocabulary App

A lightweight vocabulary learning app with system tray and spaced repetition. Supports Linux desktop (XFCE, GNOME, etc.) and macOS with GTK. You control what you learn. Period.

## Features

- **System tray**: Runs in background with tray icon
- **Save phrases**: Select text anywhere, press a hotkey, done
- **Spaced repetition**: Words with fewest reviews first, then least recently seen
- **Auto-translation**: Automatic translation via multiple providers
- **Multiple translation providers**: Google (direct), Google (deep-translator), MyMemory — with automatic fallback if one is blocked
- **Stats dashboard**: See words learned, streak, reviews today
- **Word Browser**: View, search, edit and delete all words
- **Words Added Today**: Quick view of today's vocabulary
- **Word of the Day**: Daily vocabulary boost with CEFR-level words (A1-C2)
- **Autostart**: Automatically starts on login
- **Multiple languages**: Support for 9 target languages
- **Custom data directory**: Store database anywhere (e.g., Dropbox for sync)
- **Cross-platform**: Works on Linux and macOS

## Screenshots

### Popup Notification
![Popup](docs/screenshot-popup.png)

### Add Word Dialog
![Add Word](docs/screenshot-add-word.png)

### Settings Window
![Settings](docs/screenshot-settings.png)

### Statistics Window
![Stats](docs/screenshot-stats.png)

### Word Browser
![Word Browser](docs/screenshot-word-browser.png)

### Popup Translation Message
![Stats](docs/screenshot-message.png)

## GUI App (Recommended)

Located in `src/` folder - modern GTK3 interface with system tray.

### Setup

```bash
./setup.sh
```

This will create a virtual environment and install all dependencies:
- `requests` - HTTP library
- `sqlalchemy` - Database ORM
- `deep-translator` - Translation library
- `pytest` - Testing framework
- `pytest-mock` - Mock support
- `pytest-cov` - Coverage reports

#### Platform-specific dependencies

**Linux (apt):** `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`, `gir1.2-appindicator3-0.1`

**Linux (pacman):** `python-gobject`, `gtk3`, `libappindicator-gtk3`

**macOS (Homebrew):** `gtk+3`, `pygobject3`, `adwaita-icon-theme`

### Running

```bash
source venv/bin/activate
python3 src/vocab_gui.py
```

### Keyboard Shortcuts

#### Linux

Configure in your desktop environment settings (usually Settings → Keyboard → Shortcuts):

| Command | Purpose |
|---------|---------|
| `python3 /path/to/src/vocab_cli.py --save` | Save selected text |
| `python3 /path/to/src/vocab_cli.py --delete` | Delete current word |
| `python3 /path/to/src/vocab_cli.py --next` | Show next word |

#### macOS

Configure via System Settings → Keyboard → Shortcuts → Services, or use tools like Hammerspoon or Karabiner-Elements. The same CLI commands apply:

| Command | Purpose |
|---------|---------|
| `python3 /path/to/src/vocab_cli.py --save` | Save clipboard text |
| `python3 /path/to/src/vocab_cli.py --delete` | Delete current word |
| `python3 /path/to/src/vocab_cli.py --next` | Show next word |

### Settings

- **Review interval**: How often the background loop checks for words (30min - 8hours)
- **Translation provider**: Choose between Google Translate (direct), Google Translate (deep-translator), or MyMemory (free). If the selected provider fails, the app automatically falls back to the next working one.
- **Target language**: Translation language (Russian, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Korean)
- **Word of the Day**: Enable/disable daily word notifications with CEFR level selection (A1-C2)
- **Autostart**: Automatically starts on system login
- **Custom data directory**: Store database elsewhere

### Database Location

- **Linux default**: `~/.local/share/vocab_app/vocab.db`
- **macOS default**: `~/Library/Application Support/vocab_app/vocab.db`
- Can be changed in settings

## Spaced Repetition

Words are shown fewest-reviews-first — never-reviewed words first, then oldest `last_reviewed` timestamp. Reviewing a word simply records the timestamp and increments the review count.

## Troubleshooting

### Linux

#### No popup appears
- Make sure `notify-send` is installed: `sudo apt install libnotify-bin`
- Check that desktop notifications are enabled in your system settings

#### Icons not showing
- If tray icon or popup icon doesn't appear, check file permissions on `icons/` folder

### macOS

#### GTK not found
- Make sure GTK is installed via Homebrew: `brew install gtk+3 pygobject3`
- Ensure the venv was created with `--system-site-packages`

#### No notifications
- Check that notifications are allowed for "Script Editor" in System Settings → Notifications

#### Tray icon not appearing
- GTK StatusIcon may not appear in the macOS menu bar by default. If the tray icon is missing, you can still run the app and interact via notifications and CLI commands.

### General

#### Words don't appear in review
- The app shows all your words, fewest reviews first, then least recently seen
- Make sure your target language matches the translations you want to review

## Architecture

```
src/
├── application/           # Service layer (business logic)
│   ├── factory.py         # ServiceFactory - creates services with DI
│   ├── export_service.py  # Export use case with injected CSV writer
│   ├── notification_service.py
│   ├── review_scheduler.py  # Background review loop + pause/WOTD
│   ├── review_service.py  # Review scheduling
│   ├── settings_service.py
│   ├── service_interfaces.py  # Abstract interfaces
│   ├── translation_test_service.py
│   ├── vocab_service.py   # Facade over all services
│   ├── word_service.py    # Word CRUD operations
│   └── wotd_service.py    # Word of the Day
│
├── domain/                # Domain layer (pure business rules)
│   ├── entities.py       # Word, Language, Stats, etc.
│   ├── exceptions.py     # TranslationError
│   └── repositories.py  # Abstract repository interfaces
│
├── infrastructure/        # Infrastructure layer (external systems)
│   ├── translation.py    # Translation API implementations
│   ├── models.py         # SQLAlchemy ORM models
│   ├── mappers.py        # ORM ↔ Entity mappers
│   ├── word_source.py    # LocalWordSource (CSV-backed WOTD)
│   └── ...
│
├── repositories/          # Data access implementations
│   ├── base.py           # AbstractDatabase interface
│   ├── language_repository.py
│   ├── settings_repository.py
│   ├── sqlite.py         # SQLite implementation
│   ├── stats_repository.py
│   ├── word_repository.py
│   └── wotd_repository.py
│
├── bootstrap.py          # Composition root and startup initialization
├── vocab_gui.py          # GTK3 GUI entry point
└── vocab_cli.py          # CLI entry point (hotkeys)
```

### Dependency boundaries

`bootstrap.py` is the composition root used by the GUI and CLI. It creates the
SQLite repositories and external adapters, initializes defaults, and injects
them into application services. Importing `application` does not load GTK,
SQLAlchemy, translation clients, or filesystem adapters.

The domain contains entities and repository contracts. Application services
coordinate use cases through those contracts and injected callbacks. Concrete
storage, JSON configuration, current-phrase state, CSV output, translation,
clipboard, notifications, and database relocation live in outer adapters.
Settings keys and defaults remain in the dependency-free `config.py` module.

Review ordering is owned by the repository query, notification review tracking
by `NotificationService`, and settings normalization by the typed settings
getters. All services created by one factory share one settings service.

See [the project-wide architecture review](docs/architecture-review.md) for the
SOLID, Clean Architecture, KISS, and DRY assessment and validation limits.

## Testing

### Run tests

```bash
source venv/bin/activate
pytest
```

### Test structure

```
src/tests/
├── conftest.py           # Fixtures
├── domain/               # Domain entity tests
│   └── test_entities.py
├── integration/          # Integration tests
│   └── test_repository.py
└── unit/                 # Unit tests
    ├── test_application_init.py
    ├── test_config.py
    ├── test_export_service.py
    ├── test_review_service.py
    ├── test_settings_service.py
    ├── test_sqlite.py
    ├── test_version.py
    ├── test_vocab_cli.py
    ├── test_vocab_service.py
    ├── test_word_service.py
    └── test_wotd.py
```

### CI

Tests run automatically on GitHub Actions (see `.github/workflows/test.yml`).

