# Google Apps Script operations

## Table of Contents

- [Trigger behavior](#trigger-behavior)
- [Manual run](#manual-run)
- [Import audit log](#import-audit-log)
- [Failures and retries](#failures-and-retries)
- [Security boundary](#security-boundary)

## Trigger behavior

The installed trigger runs every 12 hours by default. It takes a script lock, scans the
configured bounded Gmail query, validates each candidate URL, fetches each new
Tricount registry, then writes raw JSON and attachments to Drive.

An already processed `(Gmail message ID, public share key)` pair is skipped.
The durable processed-record list retains the newest 1,000 records.
The corresponding Gmail thread receives the configured processed label only
when every message in the thread was scanned and every detected Tricount URL
was exported or already known. The message cap prevents the next thread from
starting, but a thread already in progress is always scanned completely.
The script preserves every message's existing read state. With the default
configuration it then archives the thread, so it leaves Inbox and remains
available through the processed label.

## Manual run

Open the standalone `Tricount-Exporter` Apps Script project and run
`runThreeCountExporter`. This uses the same lock and idempotency state as the
12-hour trigger.

Use `getThreeCountSetupStatus` or `validateThreeCountExporterInstallation` for
a read-only setup check.

## Import audit log

The selected output root contains `tricount-exporter-import-log.csv`. A new
successful import appends its timestamp, Tricount title and URL, export folder
URL, source Gmail message URL and ID, attachment counts, and an empty error
field. A failed import appends the same traceability fields where available and
the failure message. Idempotent skips are not logged again.

The file is ordinary CSV rather than a Google Sheet, so it can be opened in
Sheets, Excel, or another CSV reader without an additional service.

## Success notifications

After a successful import, the script sends a concise email containing the
Tricount title, output-folder URL, source Tricount URL, source Gmail URL, and
attachment counts. Notification delivery is audit metadata: a mail failure does
not undo an otherwise successful import.

## Failures and retries

- A Tricount API failure leaves the pair unprocessed, so a later run retries it.
- A receipt failure is written into `tricount-info.json`; the raw JSON remains
  available and the invitation is treated as exported.
- The message target stops before starting another Gmail thread; the attachment
  cap remains strict.
- Trigger reconciliation creates the replacement before deleting the old trigger
  and requires exactly one valid 12-hour handler.

## Security boundary

The script requires Gmail access because Apps Script `GmailApp` currently uses
the broad Gmail scope. It processes only the configured account, saves no email
body, trusts no URL outside the exact Tricount domain boundary, and writes only
to its dedicated Drive root. Public share URLs grant data access; keep the Drive
folder private and revoke a share link in Tricount if it was sent in error.

The manifest requests only the Gmail, Drive, outbound-request, mail-send, and
trigger-management scopes used by the automation. It does not request the
Google Cloud Platform scope.
