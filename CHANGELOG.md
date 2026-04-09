# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [0.1.0] - 2026-04-09 - initial standalone rewrite

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
