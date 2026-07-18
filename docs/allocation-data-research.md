# Tricount Allocation Data Research

## Table of Contents

- [Conclusion](#conclusion)
- [What the Program Downloads](#what-the-program-downloads)
- [Sanitized Live Verification](#sanitized-live-verification)
- [Where the Original Standard CSV Lost the Data](#where-the-original-standard-csv-lost-the-data)
- [Relevant Payload Fields](#relevant-payload-fields)
- [Are Other Endpoints or Files Required?](#are-other-endpoints-or-files-required)
- [Implemented Output Strategy](#implemented-output-strategy)
- [Sources](#sources)

## Conclusion

The unequal allocation is present in the registry JSON returned by Tricount.
No additional endpoint or file is needed to obtain it.

The standard CSV is not downloaded from Tricount. `tricount-exporter` generates
it locally from the JSON response. The original formatter discarded allocation
amounts; the extended human-readable CSV preserves them per participant.

For the expense shown in the screenshot, the live API response contains the
following allocation structure. Descriptive and participant data has been
anonymized; the amounts are retained because they demonstrate the split:

| Field | Value |
| --- | --- |
| Description | `Example uneven expense` |
| Date | `2026-01-15 12:00:00.000000` |
| Payer | Participant B |
| Total | EUR 36.00 |
| Participant A allocation | EUR 29.00 |
| Participant B allocation | EUR 7.00 |
| Allocation type | `AMOUNT` for both participants |

Therefore, this is an exporter-format omission, not missing data in Tricount's
shared-link response.

## What the Program Downloads

The flow is:

1. `POST https://api.tricount.bunq.com/v1/session-registry-installation`
   creates an anonymous registry session.
2. The response supplies a session token and numeric user ID.
3. The program requests:

   ```text
   GET https://api.tricount.bunq.com/v1/user/<user_id>/registry?public_identifier_token=<shared-key>
   ```

4. That request returns JSON containing the complete registry, including
   members, entries, allocations, allocation amounts, allocation modes, and
   attachments.
5. Python's `csv.writer` creates the CSV locally.

The current implementation documents this directly in its
[authentication and registry request code][current-fetch] and its
[CSV writer][current-csv]. The original upstream program follows the same
[registry request][upstream-fetch] and [local CSV generation][upstream-csv].

The public Tricount URL is therefore an access token used to request the JSON
registry. It is not the URL of a pre-generated CSV file.

## Sanitized Live Verification

On 2026-07-18, a read-only request was made with a locally stored shared key.
No title, key, session token, original description, date, or participant name
is recorded in this document.

The matching `RegistryEntry` returned:

```json
{
  "amount": {"currency": "EUR", "value": "-36.00"},
  "allocations": [
    {
      "participant": "Participant A",
      "amount": {"currency": "EUR", "value": "-29.00"},
      "amount_local": {"currency": "EUR", "value": "-29.00"},
      "type": "AMOUNT",
      "share_ratio": null
    },
    {
      "participant": "Participant B",
      "amount": {"currency": "EUR", "value": "-7.00"},
      "amount_local": {"currency": "EUR", "value": "-7.00"},
      "type": "AMOUNT",
      "share_ratio": null
    }
  ]
}
```

This result also explains how the mobile app reconstructs the screen after a
participant opens the shared URL: the same registry payload already contains
the complete per-participant allocation list.

A public upstream sample independently confirms the payload model. Its Hotel
entry has a total of USD 85 and four allocations: three USD 20 `RATIO`
allocations and one USD 25 `AMOUNT` allocation, all inside the same
`RegistryEntry` response object [upstream-payload].

## Where the Original Standard CSV Lost the Data

The original parser initially performed the correct extraction:

```python
shares = {
    participant_name: abs(float(allocation["amount"]["value"]))
    for allocation in transaction["allocations"]
}
```

The resulting internal `Shares` mapping would be:

```text
{"Participant A": 29.0, "Participant B": 7.0}
```

This is visible in the current [allocation parser][current-parser].

The loss happened later in `prepare_transaction_data()`. It iterated over that
mapping but keeps only participant names whose amount is positive:

```python
involved = ", ".join(
    name for name, amount in transaction["Shares"].items() if amount > 0
)
```

The old CSV row consequently contained the participant names, not the
corresponding 29 and 7 values. The row construction is shown in the v0.1.0
[standard-row formatter][historical-row]. This behavior was inherited from the
[upstream row formatter][upstream-row].

## Relevant Payload Fields

Each item in `Registry["all_registry_entry"]` wraps a `RegistryEntry`. The
fields relevant to allocation fidelity are:

| JSON path relative to `RegistryEntry` | Meaning |
| --- | --- |
| `amount.value` | Total converted to the registry/base currency; returned with Tricount's sign convention |
| `amount.currency` | Registry/base currency |
| `amount_local` | Total in the original transaction currency |
| `membership_owned...alias.display_name` | Payer |
| `allocations[]` | One allocation object per included participant |
| `allocations[].membership...alias.display_name` | Allocated participant |
| `allocations[].amount.value` | Participant allocation converted to the registry/base currency |
| `allocations[].amount.currency` | Registry/base currency for the allocation |
| `allocations[].amount_local` | Participant allocation in the original transaction currency |
| `allocations[].type` | Split mode, observed as `AMOUNT` or `RATIO` |
| `allocations[].share_ratio` | Ratio weight when the allocation uses `RATIO`; absent or null for `AMOUNT` |

For accounting output, `allocations[].amount` is the authoritative resolved
amount to export. `type` and `share_ratio` are useful if the output must also
preserve how the split was entered. The public upstream payload demonstrates
both allocation modes and their fields [upstream-payload].

Tricount's official help center also confirms the product semantics: an uneven
split can be entered either by editing each participant's share or by entering
individual amounts [official-uneven-split].

## Are Other Endpoints or Files Required?

No, not for per-participant allocation data.

The single registry request already returns the allocations for every registry
entry. The program's own parser consumes them, proving that they arrive before
CSV generation. Searching bunq's public API documentation did not reveal a
separate Tricount allocation or CSV-export endpoint; the documented public bunq
API is a separate banking API surface [bunq-api].

Attachments are the only related objects that require separate downloads: the
registry JSON supplies their URLs, and the exporter optionally fetches those
binary files. That has no bearing on expense allocations.

Tricount's own help center says CSV/PDF export was removed from the current app
and directs users who require CSV or ODF to support [official-export]. This is
additional evidence that the file produced here is not a current official
Tricount CSV download.

## Implemented Output Strategy

| Rank | Option | Result |
| --- | --- | --- |
| 1 | Extended standard CSV | Writes base/local shares, allocation type, and ratio per participant. |
| 2 | Sesterce CSV | Writes exact `Paid for <participant>` amounts in the original currency. |
| 3 | Raw response JSON | Preserves every registry field as the lossless source. |

Both CSV formatters now expand the allocation objects per participant. The
human CSV also retains base/local amounts, split method, ratio, custom category,
identifiers, timestamps, status, and exchange rate.

Raw JSON can be retained with `--save-response` and remains the canonical,
lossless archive from which the CSV files can be regenerated.

## Sources

- Live Tricount registry response, read-only verification on 2026-07-18.
  Sensitive shared keys and session tokens were not retained in this report.
- [`tricount-exporter` source][current-source].
- [Original `MrNachoX/tricount-downloader` source][upstream-source].
- [Original public sample registry payload][upstream-payload].
- [Tricount help: managing expenses and uneven splits][official-uneven-split].
- [Tricount FAQ: current export availability][official-export].
- [bunq public API documentation][bunq-api].

[bunq-api]: https://doc.bunq.com/api-reference/start-here
[current-csv]: ../src/tricount_exporter/cli.py
[current-fetch]: ../src/tricount_exporter/cli.py
[current-parser]: ../src/tricount_exporter/cli.py
[current-source]: ../
[historical-row]: https://github.com/marcomc/tricount-exporter/blob/6b02efa42f081542dbd9ea269c376d025b73ed9b/src/tricount_exporter/cli.py#L342-L361
[official-export]: https://help.tricount.com/articles/tricount-faqs
[official-uneven-split]: https://help.tricount.com/articles/how-can-i-manage-my-tricounts-and-expenses
[upstream-csv]: https://github.com/MrNachoX/tricount-downloader/blob/cf9a7e68b91a1aa4041c6492b04c9796d03256e6/main.py#L214-L238
[upstream-fetch]: https://github.com/MrNachoX/tricount-downloader/blob/cf9a7e68b91a1aa4041c6492b04c9796d03256e6/main.py#L35-L45
[upstream-payload]: https://github.com/MrNachoX/tricount-downloader/blob/cf9a7e68b91a1aa4041c6492b04c9796d03256e6/response_data.json#L130-L276
[upstream-row]: https://github.com/MrNachoX/tricount-downloader/blob/cf9a7e68b91a1aa4041c6492b04c9796d03256e6/main.py#L124-L146
[upstream-source]: https://github.com/MrNachoX/tricount-downloader/tree/cf9a7e68b91a1aa4041c6492b04c9796d03256e6
