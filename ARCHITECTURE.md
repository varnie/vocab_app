# Architecture and project principles

Read this document before any work on vocab_app.

The purpose is to preserve design intent and avoid repeated rewrites. Decisions
can change to meet a concrete requirement or fix a demonstrated problem: explain
the consequences and update the relevant section. Explicit user instructions take
priority. If the code and this document disagree, investigate the reason before
deciding which needs to change.

## Product direction

vocab_app is a small desktop application for a personal vocabulary: save selected
text, obtain or enter a translation, encounter words through unobtrusive
notifications, and manage the library. GTK3 and the system tray are the main
interface; the CLI also supports desktop hotkeys. Data lives locally in SQLite,
in a directory the user can choose.

Priorities are data preservation, predictable behavior, a simple interface, and
compact code that a developer can understand. Features must serve an actual user
need. Extra modes, settings, and infrastructure for hypothetical future uses are
outside the current scope.

## Boundaries and ownership

| Area | Responsibility and constraints |
| --- | --- |
| `src/domain/` | Entities, exposure policy, time helpers, and repository contracts. Depends only on the standard library and domain. |
| `src/application/` | Use cases and coordination. May depend on domain, application, the standard library, and pure `config.py`. No GTK, SQLAlchemy, HTTP clients, or filesystem adapters. |
| `src/repositories/`, `src/infrastructure/` | Queries, transactions, ORM, providers, files, notifications, clipboard, and OS integration. Repository results use domain data rather than ORM objects. |
| `src/windows/`, `src/vocab_gui.py`, `src/vocab_cli.py` | User input and presentation. Windows use services without reaching into repositories, database sessions, or translation adapters. |
| `src/bootstrap.py` | Shared composition root for GUI and CLI: creates adapters, injects dependencies, and initializes defaults. |

- `VocabService` exposes named services and owns the shared database lifecycle.
  Access is explicit, without dynamic `__getattr__` forwarding. Dependency wiring
  belongs in the composition root.
- Services share one `SettingsService`. Keys and defaults live in pure `config.py`;
  typed settings getters own normalization.
- Internal services use concrete types. Contracts belong at storage and external
  dependency boundaries; a callable is enough for a simple injected operation.
  There is no need for a DI framework or an interface for every class.
- Repository queries own queue ordering and sorting before limits are applied.
  Do not sort an already limited subset again in a service or window.
- Review exposures from GUI and CLI use `NotificationService`.
  Callers must not duplicate exposure tracking.

## Behavior to preserve

### Exposures and notifications

- Learning uses passive exposures without required answers or ratings. Successful
  notification delivery does not prove that the user read or learned a word.
- Eligibility intervals after successive exposures are 4 hours, 1 day, 3 days,
  7 days, then at most 14 days. History is shared across translation languages;
  eligible words need a translation in the selected language. When due words
  exist, a new word follows three other exposures since the previous introduction.
  Otherwise, unseen words can fill the queue, oldest additions first.
- The queue derives its state from persisted history. A long absence does not
  trigger a burst of notifications. Notification cadence and word eligibility
  remain separate; manual Next also respects eligibility.
- For review exposures, history and the last-exposure timestamp are committed
  together after successful delivery; current-phrase state then updates as well.
  Failed delivery leaves the word eligible and does not consume an exposure.
  Saving a phrase is a separate action and does not record an exposure.
- Pause/Resume is an immediate toggle without a dialog or duration input. Pause
  survives restarts. Quiet hours are separate; manual Next works during both.
  Snoozing a word does not record an exposure.
- Word of the Day uses an English source and its own UTC-day schedule. Its
  candidate and available translation persist for retries that day. The day is
  marked shown only after successful delivery. Saving WOTD must not overwrite an
  existing user translation.
- Background failures must be visible and recoverable. The scheduler retries
  with a delay; three errors do not permanently stop it. Settings changes
  invalidate results selected under the previous settings.

### Editing, translation, and storage

- Preserve original capitalization. Search and duplicate lookup are Unicode
  case-insensitive. Translations belong to specific languages.
- `prepare_word` and `translate_preview` do not write to the vocabulary. Saving
  commits the change; late results from a closed dialog are discarded. Failed
  automatic translation must not silently create an empty entry. Saving without
  translation is an explicit user action.
- `WordRepository.save_word` is the shared creation/reuse path, including
  `translation=None`. Keep a single path for this operation.
- Deleting one language's translation preserves the phrase and other translations.
  Whole-word undo uses a typed snapshot to restore translations, history,
  statistics, timestamps, and snooze. Conflicting newer data must not be overwritten.
- A directory change takes effect at the next GUI startup before opening the
  database. SQLite backup includes committed WAL data, retains the original, and
  never overwrites an existing destination. Failure leaves the original library active.
- Today's statistics and additions use the local day. WOTD intentionally uses UTC.

### Background work

- Network translation must not block GTK. Widget updates run on the main thread
  through GLib; completed tasks must not touch closed windows.
- External operations have finite timeouts. Normal translation uses provider
  fallback; Test API checks only the selected provider.
- The scheduler releases sessions before waiting, wakes on settings changes, and
  joins workers before the shared database closes. Preserve these guarantees
  when simplifying code.

## Keeping the code compact

- Solve the requested problem with the smallest coherent change. Avoid unrelated
  project-wide cleanup, renaming, or file moves based on stylistic preference.
- Look for an existing execution path before adding one. Every abstraction needs
  a current responsibility. Avoid unused wrappers, generic managers, configuration
  options, and extension mechanisms.
- Remove proven redundant APIs, parameters, duplication, and tests that only
  verify mock behavior. Search all callers, including the CLI and tests, first.
- Prefer direct, readable code. Do not compress expressions or merge layers just
  to reduce line or file counts. Small methods that express a useful boundary
  are legitimate; size alone is not a defect.
- Optimize demonstrated problems. For the queue, consider queries and indexes
  first, keeping history as the source of state. New caches or counters need a
  reason and consistency rules.
- Refactoring preserves user-visible behavior. Describe bug fixes and new features
  separately from structural changes so their effects can be reviewed.
- A different preferred implementation style is insufficient reason to revisit
  a decision. Changes need a concrete requirement or demonstrated problem.

## Change and validation workflow

1. Read this document, check the working tree, and trace the affected scenario
   from GUI/CLI to storage or external effects.
2. Identify the benefit and guarantees to preserve. For broad requests to suggest
   improvements, propose priorities first. Once authorized, complete the agreed
   scope without asking again about routine implementation details.
3. Validate according to risk. For code changes, use `venv/bin/python -m pytest`,
   `ruff check .`, and `git diff --check`. Run the full main suite when shared
   contracts change. `src/tests/unit/test_architecture.py` checks dependency boundaries.
4. Exercise relevant behavior and failures using temporary SQLite databases with
   the production adapter. Cover delivery failure, translation cancellation, or
   restoration when affected. Run GTK checks on an isolated Broadway/Xvfb display
   with `RUN_GTK_TESTS=1`; reproduce CI issues with Xvfb and `G_DEBUG=fatal-criticals`.
   Test cleanup must not destroy GTK-owned helper windows.
5. Never use the user's live library for tests. Report what was verified and any
   untested boundaries: unit tests cannot prove real tray, network provider, or
   other-OS behavior. Documentation-only edits do not require application tests.
6. Update this file in the same task when an agreed decision changes. Keep the
   current decision and its rationale; remove superseded text without archiving it.

## Dependencies, versioning, and documentation

- Python 3.10 is the minimum. Runtime dependencies live in `requirements.txt`;
  `requirements-dev.txt` adds test tools. Package metadata reads the runtime file.
- GUI/CLI show the short HEAD hash, or `unknown` without Git. Python metadata uses
  `version.__version__`: `0+g<hash>` or `0+unknown`. Git is the version source;
  CI does not create commits or force-push to update version metadata.
- Keep project Markdown documentation in English.
- [README.md](README.md) describes usage and test commands. This document holds
  current agreements; source and tests provide verification.
