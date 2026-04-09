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
- [Development](#development)
- [Disclaimer](#disclaimer)

## Overview

`tricount-exporter` fetches transactions from a shared Tricount using its
public key, exports the ledger to CSV, and can optionally download
attachments, write Excel output, save the raw API response, and generate a
Sesterce-compatible CSV.

The key change in this version is that the Tricount key is no longer embedded
in the script. Pass it with `--key`, or set a default in a config file.

This repository started from a fork of
[`MrNachoX/tricount-downloader`](https://github.com/MrNachoX/tricount-downloader).
`tricount-exporter` is a standalone rewrite with its own tooling, defaults, and
maintenance direction.

> **Disclaimer:** tricount-exporter is an independent, community-developed
> project and is **not** affiliated with, endorsed by, or in any way
> officially connected with Tricount, bunq, or the upstream maintainer of
> `MrNachoX/tricount-downloader`. "Tricount", bunq, and related marks remain
> the property of their respective owners. This tool references publicly
> accessible shared-link data only to help users export data they already have
> access to.

## Features

- Accepts the Tricount key from the command line or config file.
- Creates a dedicated output directory for each Tricount title.
- Exports transactions to CSV by default.
- Optionally exports Excel and Sesterce-compatible CSV files.
- Optionally downloads attachments into the title-based export folder.
- Can save the raw JSON API response for inspection.
- Installs as a reusable local CLI under `~/.local/bin/tricount-exporter`.

## Requirements

- macOS or Linux
- Python 3.11+
- `markdownlint` for Markdown validation
- `shellcheck` for shell script validation

## Install

Clone the repository and install from the project root:

```bash
git clone <repo-url>
cd tricount-exporter
make install
```

`make install`:

- creates `.venv`
- installs the package in editable mode
- links the CLI to `~/.local/bin/tricount-exporter`
- installs a default config template to
  `~/.config/tricount-exporter/config.toml` if one does not exist yet

If `~/.local/bin` is not on your `PATH`, `make check-deps` tells you what to
add to your shell profile.

You can also run the installer wrapper directly:

```bash
./scripts/install.sh
```

## Configuration

The CLI reads optional configuration from:

- `~/.config/tricount-exporter/config.toml`
- or the file passed with `--config`

Start from the example file in this repository:

- [config.toml.example](config.toml.example)
- [config.schema.json](config.schema.json)

Example:

```toml
tricount_key = ""
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

Or use the compatibility entry point:

```bash
python main.py --key YOUR_PUBLIC_KEY
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
reference. If two different Tricounts share the same title, the second folder
gets a short key suffix so both remain isolated.

## Development

Install the dev environment:

```bash
make install-dev
```

Run checks:

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
- [pyproject.toml](pyproject.toml)

## Disclaimer

tricount-exporter is an independent, community-developed project and is not
affiliated with, endorsed by, or officially connected with Tricount, bunq, or
the upstream maintainer of `MrNachoX/tricount-downloader`. "Tricount", bunq,
and related marks remain the property of their respective owners.
