# Google Apps Script configuration

## Table of Contents

- [Local configuration](#local-configuration)
- [Script Properties](#script-properties)
- [Gmail eligibility](#gmail-eligibility)
- [Output root](#output-root)
- [Drive layout](#drive-layout)

## Local configuration

The installer creates the ignored `config.apps-script.local.json` from
`config.apps-script.example.json` when necessary.

| Key | Purpose |
| --- | --- |
| `time_zone` | IANA timezone for the time-based trigger. |
| `run_interval_hours` | Trigger interval in hours; default `12`. |
| `gmail_query` | Bounded Gmail search query. |
| `lookback_days` | Maximum invitation age to scan. |
| `max_messages_per_run` | Eligible-invitation target; threads finish atomically. |
| `max_attachments_per_run` | Hard cap for downloaded receipt files. |
| `drive_folder_name` | Private Drive root title. |
| `drive_output_folder_url` | Optional Drive folder URL used instead of the default root. |
| `processed_label_name` | Gmail label applied after a successful import. |
| `archive_processed_threads` | Archive a labeled successful thread without marking it read. |
| `notification_email` | Optional success-notification recipient; blank uses the trigger owner. |
| `send_success_notification` | Send confirmation emails after successful imports. |

## Script Properties

| Property | Purpose |
| --- | --- |
| `AUTOMATION_CONFIG_JSON` | Validated installer configuration. |
| `DRIVE_ROOT_FOLDER_ID` | Private Drive export root. |
| `TRICOUNT_PUBLIC_KEY_PEM` | Public installation key used by the Tricount session handshake. |
| `PROCESSED_RECORDS_MANIFEST_JSON` | Active idempotency-state shard list. |
| `PROCESSED_RECORDS_V2_<bank>_<index>` | Bounded shards of hashed Gmail-message/key records. |
| `PROCESSED_RECORDS_JSON` | Legacy idempotency state, migrated on the next run. |
| `INSTALLER_COMPLETED_AT` | Installation timestamp. |

`TRICOUNT_PUBLIC_KEY_PEM` is not a secret. No Tricount credential, Gmail
content, OAuth token, or private RSA key is stored in Script Properties.
Processed-record identifiers are SHA-256 hashes. Each shard stays below the
Apps Script per-property value limit, and only the newest 1,000 records are
retained.

## Gmail eligibility

The script first runs `gmail_query`, then independently requires all of:

1. Inbox message date is inside `lookback_days`.
2. Subject contains `tricount`, case-insensitively.
3. Plain body contains an HTTPS URL whose host is exactly `tricount.com` or a
   subdomain of it.
4. The URL contains a non-empty public share key.

The detector is compatible with invitations whose subject begins “Hey, I've
added you to my tricount” and whose body contains `Join: https://tricount.com/…`.
It never saves the email body.

After a successful import, the script applies `processed_label_name` to the
Gmail thread only after every message in that thread was scanned, without
changing its read state. The default is
`Tricount-Exporter/Imported`. When `archive_processed_threads` is `true` (the
default), the labeled thread is removed from Inbox while remaining unread and
available through its label or All Mail.

By default, `send_success_notification` sends a confirmation to the trigger
owner. Set `notification_email` to direct confirmations elsewhere, or set
`send_success_notification` to `false` to disable them.

## Output root

Leave `drive_output_folder_url` empty to retain the default private root named
`Tricount-Exporter` in My Drive. To export directly into an existing My Drive
or Shared Drive folder, paste its full folder URL in the local configuration:

```json
"drive_output_folder_url": "https://drive.google.com/drive/folders/FOLDER_ID"
```

Run `make apps-script-install` after changing the value. The installer validates
the URL, records the selected folder ID in Script Properties, and leaves prior
exports where they are. The Google account that owns the trigger must have
permission to create folders and files in the selected Drive folder.

## Drive layout

```text
Tricount-Exporter/
  tricount-exporter-import-log.csv
  Example-trip/
    transactions-example-trip.json
    tricount-info.json
    Attachments Example-trip/
      receipt_1.jpg
```

The export directory is title-based. If the same sanitized title belongs to a
different public key, the new directory receives a short key suffix. Metadata
records the source message ID and attachment failures without copying email
contents. The CSV audit contains one row for every new successful import and
every failed import attempt, with the Tricount URL, destination folder URL, and
source Gmail message URL. Idempotent skips do not create duplicate rows.
