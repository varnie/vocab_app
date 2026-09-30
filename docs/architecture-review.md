# Project-wide architecture review

Reviewed on 2026-09-14 across domain, application services, repositories and
mappers, GUI windows, CLI, platform adapters, configuration, setup scripts,
CI, and tests. This is an assessment of the source and tested behavior, not a
formal certification that every design decision satisfies every interpretation
of these principles.

| Principle | Findings and resulting design |
| --- | --- |
| Single responsibility | Startup wiring was embedded in the application package; file relocation in the settings window; CSV encoding in the export use case. Wiring now lives in `bootstrap.py`; relocation and CSV output have independent adapters. GUI controls still own user interaction. |
| Open/closed | Repository and translation-provider interfaces already support alternative implementations. The factory now also accepts a word source, phrase writer, and CSV writer instead of constructing concrete adapters. Adding an adapter only requires composition-root wiring. |
| Liskov substitution | Repository review ordering is explicitly part of its contract and tested against SQLite, including ties and more than 50 words. Services consume domain entities rather than ORM objects. Removed the unnecessary abstract database constructor; constructors need not share a signature. Runtime tests cover the supplied adapters, not every possible future implementation. |
| Interface segregation | The facade requires only a two-method session-lifecycle protocol rather than the full database/session API. The scheduler receives its actual services and no longer requires word-management operations just to duplicate notification behavior. Removed the unused bulk review-count API. Existing cohesive CRUD/settings interfaces remain. |
| Dependency inversion / Clean Architecture | Core modules import only the standard library, domain, application, and pure settings constants. SQLAlchemy, GTK, HTTP clients, filesystem state, JSON persistence, and CSV output are outside the core. Both entry points use the same composition root. A test checks imports across every core Python module. |
| KISS | Kept direct constructor injection and small callable ports; no DI framework or class hierarchy for single-function writers. Removed the settings TTL cache and duplicate review sorting. The small compatibility facade remains for UI/CLI callers. |
| DRY | Review priority is calculated once, in SQL before the limit. Notification state tracking/review recording has one owner. Bulk and individual settings reads use the same typed getters. Defaults initialize once at startup, and each factory shares one settings service. Existing common GTK helpers and translation normalization remain shared. |

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
the GUI uses the scheduler's persisted `pause_until` operation. Tests exercise
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
