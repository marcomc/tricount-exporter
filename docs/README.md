# Developer Docs

## Table of Contents

- [Purpose](#purpose)
- [Documents](#documents)
- [Current Maintainer Workflow](#current-maintainer-workflow)

## Purpose

This folder holds developer-facing notes for `tricount-exporter`.

Use these documents when you need implementation context that is too detailed
for the main project README, especially around API behavior and maintenance
decisions.

## Documents

- [api-research.md](api-research.md): current findings about the Tricount API,
  including the live behavior observed during the rewrite
- [allocation-data-research.md](allocation-data-research.md): allocation fields,
  currency semantics, and the raw-JSON-to-export data flow
- [sesterce-import-research.md](sesterce-import-research.md): official Sesterce
  CSV schema, field mapping, and known verification limits

## Current Maintainer Workflow

Use these project commands before handing work back:

```bash
make check
```

For local non-installed execution from the checkout:

```bash
python -m tricount_exporter --help
```
