# Project Agent Notes

## Purpose

`tricount-exporter` is a standalone rewrite of the upstream
`MrNachoX/tricount-downloader` project.

The current scope is:

- accept one or more public Tricount shared keys or shared URLs
- authenticate against the Tricount API
- fetch one or more shared Tricount registries
- export transactions into human-readable files
- optionally download attachments
- optionally emit alternate export formats
- optionally filter exported transactions by date window

This project is no longer aiming for upstream drop-in compatibility. Prefer the
smallest maintained surface that serves the rewritten CLI.

## Identity And Naming

- Project name: `tricount-exporter`
- Python package: `tricount_exporter`
- Installed CLI: `tricount-exporter`
- Module entry point: `python -m tricount_exporter`
- Default user config path: `~/.config/tricount-exporter/config.toml`
- Default runtime install path: `~/.local/share/tricount-exporter/venv`
- Default output base directory: `~/Downloads`

Keep the upstream attribution and disclaimer in user-facing docs. Do not imply
affiliation with Tricount, bunq, or the upstream maintainer.

## Current Behavior

The CLI currently supports multiple Tricount inputs per run.

Supported inputs today:

- repeated `--key`
- repeated `--url`
- `--config`
- `--output-dir`
- `--start-date`
- `--end-date`
- `--dry-run`
- `--download-attachments` or `--no-download-attachments`
- `--write-excel` or `--no-write-excel`
- `--write-sesterce` or `--no-write-sesterce`
- `--save-response` or `--no-save-response`
- `--version`

Important runtime behavior:

- Running `tricount-exporter` with no arguments prints help and exits with code
  `0`.
- A missing key or URL is an error unless `tricount_keys`/`tricount_urls` are
  set in config.
- `--dry-run` still authenticates and fetches the Tricount so the key is
  validated, but it must not create output files or directories.
- Config values are loaded first and CLI flags override them.
- `output_dir` in config supports `~` expansion.
- Exports are isolated per Tricount title, not per key or URL.
- The public key is still stored for traceability in `tricount-info.json`.
- Date filtering is applied locally after the registry payload is fetched.

## Output Layout

Exports are title-based and live under the chosen output base directory, which
defaults to `~/Downloads`.

Example layout:

```text
~/Downloads/
  City-trip/
    transactions-city-trip.csv
    transactions-city-trip.xlsx
    transactions-city-trip-sesterce.csv
    transactions-city-trip.json
    Attachments City-trip/
      receipt_1.jpg
    tricount-info.json
```

Rules:

- Directory names use a sanitized version of the Tricount title.
- Generated filenames use a lowercase title component without spaces or
  parentheses.
- The main CSV file name is `transactions-<sanitized-title>.csv`.
- Optional files use `.xlsx`, `-sesterce.csv`, and `.json` variants of the same
  stem.
- Attachments go into `Attachments <sanitized-title>/`.
- `tricount-info.json` stores:
  - original title
  - tricount key
  - download timestamp
  - source URL
- If two different Tricounts resolve to the same sanitized title, the second
  export directory gets a short key suffix, for example `City-trip-987654`.
- If that suffix is already taken by a different Tricount, increment with
  `-2`, `-3`, and so on until a free or matching directory is found.
- If the existing title directory already belongs to the same key, it is reused.

## API Notes

The implementation currently lives in
[`src/tricount_exporter/cli.py`](src/tricount_exporter/cli.py).

Current API flow:

1. Generate a random `app_installation_id` UUID.
2. Generate a fresh RSA keypair locally.
3. POST to
   `https://api.tricount.bunq.com/v1/session-registry-installation`
   with:
   - `app_installation_uuid`
   - `client_public_key`
   - `device_description`
4. Extract the session token from the response.
5. Extract the numeric `UserPerson.id` from the same response.
6. GET
   `https://api.tricount.bunq.com/v1/user/<user_id>/registry?public_identifier_token=<key>`
   using the auth token header.
7. Read the Tricount registry payload from `Response[0]["Registry"]`.

Known mobile-capture findings:

- enabling SSL proxying for `api.tricount.bunq.com` caused the app to fail its
  trust checks
- disabling SSL proxying for the API host allowed the app to log in and reach
  the live API
- the app continues to send Tricount-specific analytics and Sentry telemetry
  while logged in
- the API tunnel is visible in Proxyman, but the payload remains opaque unless
  the host is decrypted

Headers currently used by the client:

- `User-Agent: com.bunq.tricount.android:RELEASE:7.0.7:3174:ANDROID:13:C`
- `app-id: <generated uuid>`
- `X-Bunq-Client-Request-Id: 049bfcdf-6ae4-4cee-af7b-45da31ea85d0`
- `X-Bunq-Client-Authentication: <session token>` after authentication

Important assumptions in the parser:

- title is read from `Response[0]["Registry"]["title"]`
- memberships come from `registry["memberships"]`
- transactions come from `registry["all_registry_entry"]`
- per-transaction shares come from `transaction["allocations"]`
- attachment URLs come from `attachment["urls"][0]["url"]`
- participant display names must be unique because exports use them as column
  identifiers

The code currently assumes the Tricount API shape above is stable. If exports
break, inspect the live JSON first before changing transformation logic.

## Export Semantics

Default CSV:

- semicolon-delimited
- one row per transaction
- includes payer, description, date/time, base and original-currency totals,
  exchange rate, per-member shares in both currencies, allocation types and
  ratios, categories, transaction metadata, attachment names, and URLs

Excel export:

- same column set as the default CSV
- worksheet title is `Tricount Transactions`

Sesterce export:

- comma-delimited
- shaped for Sesterce import rather than archival readability
- columns are:
  - `Date`
  - `Title`
  - `Paid by <member>` for each sorted member
  - `Paid for <member>` for each sorted member
  - `Currency`
  - `Category`
- `Exchange rate`
- uses original transaction currency and original-currency allocation amounts
- `BALANCE` uses its custom category or falls back to `Money Transfer`
- `INCOME` negates the paid-for amounts

## Installation Modes

There are two distinct installation flows.

Final-user install:

- command: `make install`
- installs the package into `~/.local/share/tricount-exporter/venv`
- links `~/.local/bin/tricount-exporter` to that standalone runtime
- should keep working even if the repository checkout is deleted or moved

Contributor install:

- command: `make install-dev`
- uses the repo-local `.venv`
- intended for linting, tests, and local development
- does not define the durable user-facing install

If changing packaging, preserve the standalone runtime behavior of
`make install`.

## Quality Gates

Minimum checks expected after code or doc changes:

- `make check`

Use each virtual environment's Python to invoke pip (`python -m pip`) rather
than assuming a `bin/pip` script exists across supported Python versions.

Current quality tooling:

- Ruff for Python linting and formatting checks
- MyPy for Python static typing
- `pytest` for regression tests
- `markdownlint` for Markdown
- `shellcheck --enable=all` for shell scripts

Project-wide policy also requires:

- no personal Tricount keys in committed files
- no generated exports in Git
- no user-specific absolute paths in repo configuration or documentation,
  except where required for clickable local file references during agent output

## Regression Tests

Current regression coverage lives in [`tests/test_cli.py`](tests/test_cli.py).

The tests currently cover:

- help output when called with no args
- `--version`
- CSV export generation
- attachment download path behavior
- metadata file creation
- optional Excel output
- optional Sesterce output
- lossless raw-response save, including when CSV date filters are active
- rich allocation, currency, category, identifier, and timestamp fields
- Sesterce expense, balance, and income amount semantics
- attachment failures preserving transaction export files
- legacy output-name cleanup
- explicit-null local-amount fallbacks
- duplicate participant-name rejection
- disabling attachments
- reading defaults from config
- `~` expansion for config-based output directories
- CLI override precedence over config values
- export directory reuse for the same title and key
- collision suffixing for different keys with the same title

When changing CLI behavior, keep tests aligned with the README and help text.

## Known Product Decisions

These decisions have already been made and should not be rediscovered:

- Use repeatable options for future multi-input support, not comma-separated
  values.
- Preferred future shape:
  - repeated `--key KEY`
  - repeated `--url URL`
- `--url` is preferred over `--link`.
- Export folders should be named after the Tricount title, not after the key.
- The key should remain stored in metadata, not exposed as the primary folder
  name.
- The no-argument CLI behavior should remain "print help".
- Generated files should stay out of Git.
- Final-user install should not depend on the repo checkout staying present.

## Known Follow-Up Work

The roadmap is tracked in [`TODO.md`](TODO.md).

The most important pending areas are:

- strengthen Python quality automation further
- continue authenticated account discovery research

## Practical Guidance For Future Agents

Before implementing changes:

- read this file
- read `README.md`
- read `docs/api-research.md`
- read `TODO.md`
- inspect `src/tricount_exporter/cli.py`
- inspect `src/tricount_exporter/__main__.py`
- inspect `tests/test_cli.py`

When updating behavior:

- update docs and tests in the same change
- keep `README.md` aligned with actual CLI behavior
- when generated filenames change, update cleanup migration, `.gitignore`,
  documentation, and regression tests together
- prepare derived attachment metadata before writing CSV or Excel consumers,
  but defer network downloads until every transaction export is written
- prefer editing the current implementation rather than reintroducing legacy
  compatibility layers
- avoid committing generated `*.egg-info` churn unless packaging metadata truly
  changed and the repo intentionally tracks it
