# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-07-18 - richer allocation exports

### Added in 0.2.0

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

### Changed in 0.2.0

- Changed generated filenames to portable lowercase names without spaces or
  parentheses, including `transactions-<title>.json` for the raw API response.
- Changed Sesterce exports to use the original transaction currency and local
  allocation amounts while retaining Tricount's historical exchange rate.
- Changed Sesterce category selection to prefer `category_custom` and use
  `Money Transfer` for balance entries without a custom category.
- Removed the configurable raw-response filename in favor of deterministic
  title-based naming.

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
