# tricount-exporter

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Install](#install)
- [Configuration](#configuration)
- [Usage](#usage)
- [Usage Examples](#usage-examples)
- [Sesterce CSV](#sesterce-csv)
- [Output Layout](#output-layout)
- [Attribution](#attribution)
- [Developer Docs](#developer-docs)
- [Development](#development)
- [Disclaimer](#disclaimer)

## Overview

`tricount-exporter` fetches transactions from a shared Tricount using its
public key, exports the ledger to CSV, and can optionally download
attachments, write Excel output, save the raw API response, and generate a
Sesterce-compatible CSV.

The key change in this version is that the Tricount key is no longer embedded
in the script. Pass one or more keys with repeated `--key` options, pass one or
more shared links with repeated `--url` options, or set defaults in a config
file.

This repository started from a fork of
[`MrNachoX/tricount-downloader`](https://github.com/MrNachoX/tricount-downloader)
by `MrNachoX`. `tricount-exporter` is a standalone rewrite with its own
tooling, defaults, and maintenance direction.

> **Disclaimer:** tricount-exporter is an independent, community-developed
> project and is **not** affiliated with, endorsed by, or in any way
> officially connected with Tricount, bunq, or the upstream maintainer of
> `MrNachoX/tricount-downloader`. "Tricount", bunq, and related marks remain
> the property of their respective owners. This tool references publicly
> accessible shared-link data only to help users export data they already have
> access to.

## Features

- Accepts one or more Tricount keys or shared links from the command line or
  config file.
- Creates a dedicated output directory for each Tricount title.
- Exports transactions to CSV by default.
- Optionally exports Excel and Sesterce-compatible CSV files.
- Optionally downloads attachments into the title-based export folder.
- Can save the raw JSON API response for inspection.
- Can filter exported transactions by date range.
- Installs as a reusable local CLI under `~/.local/bin/tricount-exporter`.

## Requirements

For end users:

- macOS or Linux
- Python 3.11+
- `make`

For contributors:

- `markdownlint` for Markdown validation
- `mypy` through the project virtual environment
- `shellcheck` for shell script validation

## Install

For a normal user install, clone the repository, run the installer once, and
then use the installed CLI from anywhere:

```bash
git clone <repo-url>
cd tricount-exporter
make install
```

`make install`:

- creates a standalone runtime environment in
  `~/.local/share/tricount-exporter/venv`
- installs the package into that runtime environment
- links the CLI to `~/.local/bin/tricount-exporter`
- installs a default config template to
  `~/.config/tricount-exporter/config.toml` if one does not exist yet

If `~/.local/bin` is not on your `PATH`, `make check-deps` tells you what to
add to your shell profile.

This means the installed `tricount-exporter` command keeps working even if you
later delete or move the source checkout.

You can also run the installer wrapper directly:

```bash
./scripts/install.sh
```

Verify the install:

```bash
tricount-exporter --version
tricount-exporter
```

The second command prints the help text when you run it without parameters.

## Configuration

The CLI reads optional configuration from:

- `~/.config/tricount-exporter/config.toml`
- or the file passed with `--config`

Start from the example file in this repository:

- [config.toml.example](config.toml.example)
- [config.schema.json](config.schema.json)

Example:

```toml
tricount_keys = []
tricount_urls = []
start_date = "2026-04-01"
end_date = "2026-04-30"
output_dir = "~/Downloads"
download_attachments = true
write_excel = false
write_sesterce = false
save_response = false
response_file_name = "response_data.json"
```

## Usage

### Find Your Tricount Key

1. Open your Tricount.
2. Share the Tricount via a public link.
3. Copy the part after `https://tricount.com/`.

If your shared link is `https://tricount.com/YOUR_PUBLIC_KEY`, the key is
`YOUR_PUBLIC_KEY`.

### Run From The CLI

Use a key directly:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY
```

Export multiple Tricounts in one run:

```bash
tricount-exporter \
  --key FIRST_PUBLIC_KEY \
  --key SECOND_PUBLIC_KEY \
  --url "https://tricount.com/THIRD_PUBLIC_KEY" \
  --url "https://www.tricount.com/FOURTH_PUBLIC_KEY"
```

Filter exported transactions by date:

```bash
tricount-exporter \
  --key YOUR_PUBLIC_KEY \
  --start-date 2026-04-01 \
  --end-date 2026-04-30
```

Or run the package module directly from a checkout:

```bash
python -m tricount_exporter --key YOUR_PUBLIC_KEY
```

Enable extra outputs as needed:

```bash
tricount-exporter \
  --key YOUR_PUBLIC_KEY \
  --write-excel \
  --write-sesterce \
  --save-response
```

Disable attachments for a run:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY --no-download-attachments
```

Validate a key and preview the export paths without writing files:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY --dry-run
```

Use a specific config file:

```bash
tricount-exporter --config ./config.toml --key anotherPublicKey
```

## Usage Examples

Download one Tricount with the default settings:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY
```

Download one Tricount and save every supported export:

```bash
tricount-exporter \
  --key YOUR_PUBLIC_KEY \
  --write-excel \
  --write-sesterce \
  --save-response
```

Download one Tricount without attachments:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY --no-download-attachments
```

Use a local config file but override the key for the current run:

```bash
tricount-exporter --config ./config.toml --key YOUR_PUBLIC_KEY
```

Write exports to a custom directory instead of `~/Downloads`:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY --output-dir ./exports
```

Export multiple Tricounts from repeated inputs and let the exporter create
separate title-based folders for each one:

```bash
tricount-exporter \
  --key KEY_ONE \
  --key KEY_TWO \
  --url "https://tricount.com/KEY_THREE" \
  --url "https://tricount.com/KEY_FOUR"
```

## Sesterce CSV

A Sesterce-compatible CSV is an export shaped for import into Sesterce, which
is another shared-expense tool. It is different from the default transaction
CSV because it is organized around who paid and who each expense was paid for,
using one column set per member.

Use the default CSV when you want a readable transaction export for inspection,
archiving, spreadsheets, or your own processing.

Use the Sesterce-compatible CSV when you want to migrate data from Tricount
into Sesterce or test whether a Tricount can be reconstructed there with the
same member splits.

Enable it with:

```bash
tricount-exporter --key YOUR_PUBLIC_KEY --write-sesterce
```

## Output Layout

Each Tricount gets its own human-readable directory under `~/Downloads/` by
default, based on the Tricount title:

```text
~/Downloads/
  City-trip/
    Transactions City-trip.csv
    Transactions City-trip.xlsx
    Transactions City-trip (Sesterce).csv
    response_data.json
    Attachments City-trip/
      receipt_1.jpg
      receipt_2.pdf
    tricount-info.json
```

`tricount-info.json` keeps the public key and download timestamp as a stable
reference. If two different Tricounts share the same title, the exporter adds a
short key suffix and keeps incrementing if needed until it finds a free folder.

## Attribution

This repository is an independent rewrite inspired by the upstream project
[`MrNachoX/tricount-downloader`](https://github.com/MrNachoX/tricount-downloader)
by `MrNachoX`.

The current code, CLI shape, packaging, install flow, tests, and maintenance
direction are specific to `tricount-exporter`.

## Developer Docs

Additional maintainer-facing documentation lives in [docs/README.md](docs/README.md).

Current API findings are documented in
[docs/api-research.md](docs/api-research.md).

## Development

Install the dev environment:

```bash
make install-dev
```

`make install-dev` is for working on the repository itself. It uses the local
`.venv` and does not define the user-facing installed command.

Run the full maintainer quality gate:

```bash
make check
```

Run linting and static checks only:

```bash
make lint
```

Run regression tests:

```bash
make test
```

Useful project files:

- [AGENTS.md](AGENTS.md)
- [CHANGELOG.md](CHANGELOG.md)
- [TODO.md](TODO.md)
- [docs/README.md](docs/README.md)
- [pyproject.toml](pyproject.toml)

## Disclaimer

tricount-exporter is an independent, community-developed project and is not
affiliated with, endorsed by, or officially connected with Tricount, bunq, or
the upstream maintainer of `MrNachoX/tricount-downloader`. "Tricount", bunq,
and related marks remain the property of their respective owners.
