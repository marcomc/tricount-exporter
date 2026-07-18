# Sesterce Import Research

## Table of Contents

- [Conclusion](#conclusion)
- [Officially Supported Input](#officially-supported-input)
- [Official CSV Schema](#official-csv-schema)
- [Comparison With the Current Exporter](#comparison-with-the-current-exporter)
- [Data Fidelity](#data-fidelity)
- [Recommended Output Strategy](#recommended-output-strategy)
- [Verification Limits](#verification-limits)
- [Sources](#sources)

## Conclusion

Sesterce's documented import format is **CSV, not JSON**. The current
`transactions-<title>-sesterce.csv` uses Sesterce's recommended method and
is structurally valid:

```text
Date,Title,Paid by <member>...,Paid for <member>...,Currency,Category,Exchange rate
```

It preserves the resolved unequal allocation, including a split such as EUR 29
for Participant A and EUR 7 for Participant B, the original transaction
currency, its historical exchange rate, and the custom category name.
Transaction IDs, attachments, timestamps, and the original split method are
not part of Sesterce's documented CSV import schema.

The raw Tricount JSON and the Sesterce CSV therefore serve different purposes:

| Output | Purpose | Recommendation |
| --- | --- | --- |
| Raw Tricount JSON | Lossless archive and machine-to-machine source | Always retain |
| Sesterce CSV | Sesterce import | Generate from the raw JSON |
| Human-readable CSV | Inspection and spreadsheet analysis | Generate separately |

JSON alone is appropriate for a custom spreadsheet ingestion process, but it
cannot be uploaded directly through Sesterce's documented importer.

## Officially Supported Input

Sesterce documents importing a **CSV file** either as a new group or, since
mobile version 2.17.16, into an existing group [official-import]. When creating
a new group, members, expenses, and categories found in the CSV are created.
When importing into an existing group, missing members and categories are added
and strictly identical expenses are deduplicated.

The documentation explicitly mentions CSV migration from Tricount. It does not
document JSON import, a Sesterce JSON schema, or a facility for uploading the
original Tricount API response.

Supported separators are:

- comma;
- semicolon;
- tab;
- pipe (`|`).

The first row must be a header. Sesterce states that its documented field list
is not exhaustive, so only the fields below should be treated as a public,
supported contract [official-import].

## Official CSV Schema

### Required operation fields

| Purpose | Documented English header | Accepted value |
| --- | --- | --- |
| Date | `Date` | `YYYY-MM-DD`, `YYYY/MM/DD`, or `YYYYMMDD` |
| Title | `Title` or `Description` | Operation title |
| Amount and allocation | One of the three methods below | Numeric values |

Sesterce offers three amount representations. Method 1 is recommended.

#### Method 1: paid by and paid for

For every member `X`:

- `Paid by X`: amount advanced by that member;
- `Paid for X`: amount that member should ultimately bear.

The sum of all `Paid by` values must equal the sum of all `Paid for` values.
Amounts are positive for expenses and negative for income. This method supports
multiple payers and exact unequal allocations. The official example is:

```csv
Date,Title,Paid by Pierre,Paid by Sophie,Paid by Brad,Paid for Pierre,Paid for Sophie,Paid for Brad,Currency,Category
20230722,Hotel aBis,358.0,0.0,0.0,0.0,169.0,189.0,EUR,Hosting
```

#### Method 2: total, payer, and member allocations

- `Cost`, `Total`, or `Amount`: total operation amount;
- `Who paid`: payer name;
- one column named after each member: that member's allocation.

Member allocations must sum to the total. This representation supports only
one named payer per row.

#### Method 3: total and net member impacts

- `Cost`, `Total`, or `Amount`: total operation amount;
- one column named after each member: negative means the member must pay and
  positive means the member must recover.

Member impacts must sum to zero. Sesterce explicitly recommends avoiding this
method because it cannot describe the operation precisely.

### Optional fields

| Purpose | Documented English header | Value |
| --- | --- | --- |
| Category | `Category` | Category name |
| Currency | `Currency` | Operation currency |
| Exchange rate | `Exchange rate` | Conversion into the group's base currency |

The importer creates categories found in the file, and Sesterce supports custom
category names [official-import] [official-categories]. Consequently, Tricount
category constants such as `FOOD` are importable, but they become category
names; the CSV does not carry icon, color, category ID, or a mapping to a
specific built-in Sesterce category.

## Comparison With the Current Exporter

The current implementation writes comma-separated UTF-8 CSV with these exact
headers [current-writer]:

```text
Date
Title
Paid by <member> for every member, sorted by name
Paid for <member> for every member, sorted by name
Currency
Category
Exchange rate
```

This is a valid implementation of Sesterce method 1. For the EUR 36 example it
can represent the full allocation as:

```csv
Date,Title,Paid by Participant A,Paid by Participant B,Paid for Participant A,Paid for Participant B,Currency,Category,Exchange rate
2026-01-15,Example uneven expense,0,36,29,7,EUR,Example category,1
```

The values are produced as follows [current-row]:

- the Tricount payer receives `amount_local` in `Paid by <payer>`;
- every resolved `allocations[].amount_local.value` becomes `Paid for <member>`;
- `INCOME` negates the `Paid for` values;
- a custom category is preferred over the generic Tricount category;
- `BALANCE` without a category is assigned the text `Money Transfer`;
- `UNCATEGORIZED` is exported as an empty category.
- `exchange_rate` becomes the documented `Exchange rate` field.

The regression suite checks the Sesterce headers, original-currency amounts,
uneven splits, custom categories, and exchange rates [current-tests].

## Data Fidelity

| Tricount information | Current Sesterce CSV | Sesterce import status |
| --- | --- | --- |
| Date | Preserved as date only | Supported and required |
| Description | Preserved as `Title` | Supported and required |
| Payer | Preserved | Supported by method 1 |
| Exact participant allocation | Preserved | Supported by method 1 |
| Multiple payers | Schema supports it | Tricount parser supplies one payer |
| Currency | Preserved | Supported and optional |
| Historical exchange rate | Preserved | Supported as optional `Exchange rate` |
| Built-in category name | Preserved except uncategorized | Supported and optional |
| Custom category name | Preserved | Supported as a category name |
| Custom category icon/metadata | Dropped | No documented columns |
| Expense versus income | Encoded by amount sign | Supported by documented sign convention |
| Transfer or balance type | Replaced with category text | No documented transaction-type column |
| Tricount transaction ID/UUID | Dropped | No documented ID columns |
| Created/updated timestamps | Dropped | No documented columns |
| Time of day | Dropped | Import accepts date only |
| Attachment metadata and URLs | Dropped | No documented import columns |
| Attachment binaries | Not in CSV | Sesterce supports UI picture upload, not documented CSV picture import |
| Split mode (`AMOUNT`/`RATIO`) | Dropped | No documented column |
| Original ratio/share count | Dropped | No documented column |
| Resolved unequal split | Preserved | Fully represented by `Paid for` values |
| Notes or comments | Dropped | No documented import column |
| Original registry/member IDs | Dropped | No documented columns |

### Exchange-rate consequence

Sesterce supports an operation currency, a group base currency, and a
per-operation conversion rate [official-currencies]. The optional
`Exchange rate` import column exists specifically to convert the operation into
the group currency [official-import].

The exporter uses `amount_local` and `allocations[].amount_local` as the
original-currency amounts and writes `exchange_rate` in Sesterce's documented
column. The converted base-currency values remain available in the human CSV
and raw JSON.

### Operation-type consequence

Sesterce has three native operation types: expense, transfer between members,
and income [official-operations]. Its import documentation defines the income
sign convention but does not publish a transaction-type field or a rule saying
that category text `Money Transfer` creates a native transfer.

The current `BALANCE` conversion should therefore not be described as proven
to preserve native transfer semantics. It certainly preserves amounts and the
label `Money Transfer`; whether the importer promotes that label into a native
transfer is not covered by the public import contract.

### Split-method consequence

Sesterce itself can model share counts and fixed amounts [official-operations].
Method 1 imports only the final monetary allocation. Thus EUR 29/EUR 7 is
preserved exactly for balances and reporting, but whether Tricount originally
used fixed amounts, ratios, or a mixture cannot be reconstructed in Sesterce
from the CSV.

### Attachments and identifiers

Sesterce supports picture attachments through its operation editor, as a
Premium feature [official-pictures]. No picture, attachment URL, attachment ID,
or binary-reference field appears in the documented CSV schema.

Likewise, the importer documents strict-content deduplication for imports into
an existing group, not source-ID matching. Tricount transaction UUIDs are not
part of the supported schema and cannot be relied upon for idempotency.

## Recommended Output Strategy

| Rank | Output | Reason |
| --- | --- | --- |
| 1 | Raw Tricount JSON | Canonical, lossless source for future transforms and custom spreadsheet ingestion |
| 2 | Sesterce method-1 CSV | Direct Sesterce import with exact resolved payer/beneficiary amounts |
| 3 | Human-readable CSV | Convenient inspection without forcing Sesterce's wide member-column model |

The implemented Sesterce export adds `Exchange rate` and prefers
`category_custom`. `BALANCE` entries still use a category-name fallback because
the official import documentation does not define a native transaction-type
field.

The Sesterce CSV should remain a purpose-built import artifact. Adding arbitrary
Tricount fields to it provides no documented Sesterce benefit. Extra archival
fields belong in the raw JSON or in the human-readable analytical CSV.

## Verification Limits

No public, first-party Sesterce application or importer source repository and
no official importer test suite were discoverable. The production web app is a
compiled Kotlin/Wasm application and delegates CSV import to the Sesterce API;
the server-side parser implementation is not publicly documented.

Accordingly:

- the schema and semantics above are limited to Sesterce's official public
  documentation;
- undocumented columns must not be assumed to work;
- native transfer recognition from `Money Transfer` remains unverified;
- actual import dry-run tests should be added before claiming end-to-end
  compatibility.

## Sources

- [Sesterce official import documentation][official-import].
- [Sesterce official operations documentation][official-operations].
- [Sesterce official multiple-currencies documentation][official-currencies].
- [Sesterce official categories documentation][official-categories].
- [Sesterce official picture-attachment documentation][official-pictures].
- [`tricount-exporter` Sesterce row conversion][current-row].
- [`tricount-exporter` Sesterce CSV writer][current-writer].
- [`tricount-exporter` current regression tests][current-tests].

[current-row]: ../src/tricount_exporter/cli.py
[current-tests]: ../tests/test_cli.py
[current-writer]: ../src/tricount_exporter/cli.py
[official-categories]: https://sesterce.io/docs/categories/
[official-currencies]: https://sesterce.io/docs/multi-currencies/
[official-import]: https://sesterce.io/docs/import/
[official-operations]: https://sesterce.io/docs/operations/
[official-pictures]: https://sesterce.io/docs/picture/
