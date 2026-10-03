# Project-wide architecture review

Reviewed on 2026-09-14 across domain, application services, repositories and
mappers, GUI windows, CLI, platform adapters, configuration, setup scripts,
CI, and tests. This is an assessment of the source and tested behavior, not a
formal certification that every design decision satisfies every interpretation
of these principles.

| Principle | Findings and resulting design |
| --- | --- |
| Single responsibility | Startup wiring was embedded in the application package; file relocation in the settings window; CSV encoding in the export use case. Wiring now lives in `bootstrap.py`; relocation and CSV output have independent adapters. GUI controls still own user interaction. |
| Open/closed | Repository and translation-provider interfaces support alternative implementations. Services accept a word source, phrase writer, and CSV writer. All concrete dependencies are assembled in bootstrap; adding an adapter only requires composition-root wiring. |
| Liskov substitution | Repository review ordering is explicitly part of its contract and tested against SQLite, including ties and more than 50 words. Services consume domain entities rather than ORM objects. Removed the unnecessary abstract database constructor; constructors need not share a signature. Runtime tests cover the supplied adapters, not every possible future implementation. |
| Interface segregation | The facade requires only a two-method session-lifecycle protocol rather than the full database/session API. The scheduler receives its actual services and no longer requires word-management operations just to duplicate notification behavior. Removed the unused bulk review-count API. Existing cohesive CRUD/settings interfaces remain. |
| Dependency inversion / Clean Architecture | Core modules import only the standard library, domain, application, and pure settings constants. SQLAlchemy, GTK, HTTP clients, filesystem state, JSON persistence, and CSV output are outside the core. Both entry points use the same composition root. A test checks imports across every core Python module. |
| KISS | Kept direct constructor injection and small callable ports; no DI framework or class hierarchy for single-function writers. Removed the settings TTL cache and duplicate review sorting. UI/CLI callers access named services through `VocabService`, which owns the shared database lifecycle. |
| DRY | Review priority is calculated once, in SQL before the limit. Notification state tracking/review recording has one owner. Bulk and individual settings reads use the same typed getters. Defaults initialize once at startup; all services share one settings service. GTK button/label layout and translation normalization remain shared. |

## Layer assessment

- **Domain:** plain dataclasses, domain exceptions, UTC helpers, and repository
  contracts remain independent of infrastructure.
- **Application:** contains use-case orchestration and ports. Notification text
  remains a string-based application output; separating a complete presentation
  model would add complexity without a current second rendering requirement.
- **Repositories and mappers:** SQLAlchemy and transaction mechanics stay in
  adapters. They map ORM records into domain entities. SQLite owns efficient
  execution of the documented review-order contract.
- **GUI and CLI:** retain widget/argument handling and user feedback. They may
  import outer adapters for platform operations; dependencies never point back
  into these entry points from core modules. Relocation mechanics are testable
  without loading GTK.
- **Platform adapters:** translation providers, tray implementations, clipboard,
  notifications, autostart, and local CSV word sources already have useful
  boundaries. Platform selection and provider registration are configuration
  concerns; no generic plugin framework is needed.
- **Configuration and startup:** pure keys/defaults remain in `config.py`;
  JSON operations moved to `infrastructure/config_file.py`. Path resolution is
  shared by startup and settings through `infrastructure/data_paths.py`.
- **Setup and CI:** these are deployment tooling, outside the application
  dependency rule. Existing shell helpers already share repeated workflow
  generation. They were reviewed rather than rewritten for OO principles.

## Compatibility and verification

The 2026-09-30 review found two boundary leaks introduced by the browser
workflow. Undo now passes a typed `WordSnapshot` containing domain entities;
table names and ORM conversion stay inside the repository. Translation previews
go through `WordManagementService.translate_preview`, which validates the phrase
and selects the configured provider. The window no longer reaches into the
translation adapter. Service contracts include undo, preview, and the explicit
WOTD language arguments.

Architecture tests resolve relative imports as well as absolute imports and
check that windows do not access database sessions, word repositories, or
translation adapters directly. SQLite regression tests check that undo restores
all translations, history, statistics, and hidden dates, including after a
filtered query, and refuses conflicting records.

Cleanup removed unused CRUD and statistics methods, the scheduler's old
one-hour pause toggle and unread current-word cache, and unused domain
re-exports. The CLI still reads the current phrase through its file adapter;
the GUI uses the scheduler's persisted pause/resume toggle. Tests exercise
the current undo and review paths. The unused `pytest-mock` dependency was
removed, and CI collects coverage during its single core test run.

Internal imports changed: service creation now comes from `bootstrap`, phrase
state from `infrastructure.current_phrase`, and JSON configuration helpers from
`infrastructure.config_file`. All repository call sites and tests were updated.
Constructor callers must supply the new writer/source dependencies. Desktop
commands, database schema, and CSV column layout remain unchanged.

The automated suite covers dependency direction, real SQLite startup and review
ordering, shared settings and defaults, injected notification state, relocation
cancellation/overwrite protection, CSV output, and existing CLI behavior.
Lint, source compilation, shell syntax, and diff checks supplement those tests.
Desktop interaction on Linux/macOS and actual installation/network translation
are separate integration checks; passing unit tests does not validate them.

## Readability refactor, 2026-10-02

Removed `VocabService.__getattr__`; GUI, CLI, and tests use explicit service
attributes. Windows annotate their application dependency as `VocabService`.
Language listing, translation API testing, and database lifecycle operations
remain explicit methods on the application container.

The word browser builds filters, the word list, actions, and pagination in
separate methods. Selected-language lookup, selection reset, and search-timer
cancellation have one implementation each. Deletion refreshes the language
counts and words once. Undo uses a `WordSnapshot` or `TranslationDeletion` record.

`EditWordDialog` owns edit fields, translation preview state, validation, and
saving. It receives application services and the parent's background runner;
closed dialogs ignore late preview results. Preview does not write to the DB.

Queue and earliest-eligibility SQL queries share exposure-history aggregation
and interval expressions. Filtering, ordering, and limits remain in SQL;
transactions, ORM conversion, and undo conflict checks remain in repositories.

Settings form collection/validation and directory-choice handling have separate
methods. `SettingsRepository.set_many` commits all database settings together
and rolls back the entire batch on failure. Default initialization also uses a
batch while preserving existing preferences. JSON relocation state and OS
autostart remain separate operations outside the database transaction.

Typed settings getters and quiet-hour evaluation now live in `SettingsService`;
service interfaces contain contracts only. Quiet-hour parsing is shared with
the settings form. Word/review contracts include translation restore, snooze,
and earliest eligibility. `add_word` delegates cache lookup, automatic
translation, and selected-language result loading to explicit helpers.

The scheduler uses two persistent workers and one condition for stop/settings
wakeups. Monotonic deadlines preserve exact intervals and startup delays;
settings changes recompute cadence from the last popup. A change generation
prevents missed wakeups during work. Each iteration releases its DB session
before waiting. Stop joins both workers before the GUI closes the database and
suppresses notifications from late results. An in-flight WOTD translation must
finish or time out before shutdown completes. Settings saves notify the
scheduler through the existing window callback.

Removed redundant language-getter and snapshot wrappers. Shared fixtures reduce
the application-container tests from 164 to 57 lines. No new dependencies,
frameworks, or architecture layers were introduced.

Removed `ServiceFactory`; `bootstrap.py` directly assembles the services and
injects them into the typed `VocabService` dataclass. `TranslationTestService`
retains its separate responsibility. Abstract contracts keep ABC enforcement,
signatures, and semantic documentation while omitting repetitive method-name
descriptions. GTK helpers share button wiring and labelled rows; statistics
rows use a short loop. Detailed word mapping reuses the base mapper, and review
statistics use the domain dataclass fields via `asdict`.

This reduction pass removes 223 physical Python lines from production sources
(5588 to 5365, excluding tests). Core checks pass with 242 tests and 22 skips;
the separate Broadway run passes 20 GUI tests with one documentation skip.

Regressions cover settings rollback/recovery, quiet-hour boundaries, draft/cache
translation behavior, directory-choice cancellation/errors, scheduler cadence,
startup/stop wakeups, in-flight shutdown, and real SQLite exposure/session
cleanup. GUI startup/settings/shutdown runs with a temporary DB, an isolated
Broadway display, and a substituted tray/notification adapter. Real OS tray and
network translation remain outside these checks.

## Service and dependency cleanup, 2026-10-03

Internal services now use concrete types. Contracts remain for repositories,
translation, word sources, and database lifecycle. `prepare_word` validates and
resolves a translation without writing to the vocabulary; `add_word` saves it.
Removed the unused `force_translate` option. Fresh edit previews still use
`translate_preview` and preserve the saved translation until the user saves.

Provider names live in one table. A shared subprocess call handles timeouts,
normalization, and MyMemory language codes. Fallback order is unchanged.
The settings connection check calls the selected translator without fallback;
it no longer needs a separate service class.

GUI and CLI use the same notification operation. It records history and current
phrase only after successful delivery. WOTD uses English as its source language
and marks the day shown after its notification succeeds. Browser sizing keeps
the default dimensions when a virtual monitor reports no usable work area.

Repository fixtures use the production SQLite adapter with temporary files.
Removed tests of mock return values and ordinary attribute lookup. Regressions
cover failed notification delivery, unchanged review eligibility, GUI and CLI
delivery handling, WOTD language selection, and deferred WOTD history.

Runtime dependencies live in `requirements.txt`; `requirements-dev.txt` adds the
test tools. Project metadata reads runtime dependencies and `VERSION` from those
files. Version changes are manual release changes; the workflow that committed
and force-pushed a SHA after each push has been removed. Ruff targets Python 3.10,
matching the declared minimum version.

Validation: 244 core tests passed, with 23 opt-in tests skipped. The isolated
Broadway run passed 21 GUI tests with `G_DEBUG=fatal-criticals`; one screenshot
update test was skipped. The host's X11-only canberra module was disabled for
that process. Ruff, shell syntax, dependency resolution without installation,
and project metadata/wheel generation also passed. OS notification delivery,
network translation, macOS, and the remote CI run were not exercised.
