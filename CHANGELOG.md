# Changelog

All notable changes to this project are documented in this file.

## [0.3.0] - 2026-07-23 - `Tricount-Exporter` Google Apps Script automation

### Added

- Optional standalone `Tricount-Exporter` Google Apps Script automation.
- Gmail invitation discovery, cloud-only Tricount JSON export, receipt download,
  idempotent Drive output, time-based trigger lifecycle, and a resumable installer.
- Added a configurable Gmail import-status label, applied after successful
  imports without changing the email read state.
- Added an append-only CSV import audit with source Gmail and Tricount URLs,
  outcome, export location, attachment counts, and errors.
- Added optional Drive output-root selection by folder URL while retaining the
  default `My Drive/Tricount-Exporter` root.
- Added interactive and non-interactive Apps Script configuration for output,
  processed-mail labels, archive behavior, notifications, and interval.
- Changed the default Apps Script trigger interval from daily to every 12 hours.

### Fixed

- Fixed Apps Script invitation recognition on runtimes without the JavaScript
  `URL` global, including direct Tricount share links in real Gmail messages.
- Fixed processed-thread archiving to preserve an invitation's existing unread
  state.
- Fixed mixed-outcome Gmail threads being labeled or archived before every
  detected share URL was processed successfully.
- Removed an unused Google Cloud Platform OAuth scope from the Apps Script
  manifest.
- Fixed Gmail pagination skipping eligible invitations after earlier results
  were archived, while keeping each started thread atomic.
- Replaced the oversized single-property idempotency ledger with bounded,
  migration-compatible Script Properties shards.

## [0.2.1] - 2026-07-19 - standalone installation fix

### Fixed

- Fixed `make install` on Python distributions that provide `pip3` without a
  `pip` script in virtual environments.
- Fixed standalone installation paths containing spaces.
- Removed a machine-specific absolute path from the API research notes.

## [0.2.0] - 2026-07-18 - richer allocation exports

### Added

- Added per-member base and local shares, allocation types, and share ratios to
  the human-readable CSV and Excel exports.
- Added transaction IDs, UUIDs, timestamps, status, entry type, transaction
  type, original-currency amounts, exchange rates, and custom categories to the
  human-readable exports.
- Added the documented Sesterce `Exchange rate` field and regression coverage
  for unequal allocations, original currencies, custom categories, and balance
  category handling.
- Added research notes covering Tricount allocation data and the official
  Sesterce CSV import schema.

### Changed

- Changed generated filenames to portable lowercase names without spaces or
  parentheses, including `transactions-<title>.json` for the raw API response.
- Changed Sesterce exports to use the original transaction currency and local
  allocation amounts while retaining Tricount's historical exchange rate.
- Changed Sesterce category selection to prefer `category_custom` and use
  `Money Transfer` for balance entries without a custom category.
- Removed the configurable raw-response filename in favor of deterministic
  title-based naming.
- Changed duplicate participant display names from silent allocation merging
  to an explicit export error.

### Fixed

- Fixed attachment filenames being omitted from the human CSV and Excel files
  even when the attachments were downloaded successfully.
- Fixed attachment timeouts and HTTP failures preventing CSV, Excel, Sesterce,
  and raw JSON files from being written.
- Fixed explicit `null` local amounts and exchange rates failing instead of
  using their base-currency defaults.

## [0.1.0] - 2026-04-09 - initial standalone rewrite

### Added

- Added repeatable `--key` and `--url` inputs for multi-Tricount runs.
- Added share-link token extraction, title-based batch exports, and local
  date filtering for exported transactions.
- Updated the config schema, examples, and developer notes to match the
  current CLI behavior.

### Changed

- Renamed the rewritten project to `tricount-exporter`.
- Refactored the downloader into an installable CLI package.
- Added config-file support and `--key` input so the Tricount key is no longer hardcoded.
- Removed the leftover `main.py` compatibility entry point and standardized local execution on `python -m tricount_exporter`.
- Reduced duplicate maintained packaging surface by removing `requirements.txt` in favor of `pyproject.toml`.
- Standardized exports into title-based output folders, hardened collision handling, and kept attachment downloads inside those folders.
- Added `--dry-run` to validate shared keys and preview export paths without writing files.
- Added project scaffolding for installation, configuration, and contributor guidance.
- Added MyPy and a repeatable `make check` maintainer quality gate.
- Expanded regression coverage for config resolution and export-path behavior.
- Added developer-facing API research notes under `docs/`.
