# Google Apps Script intake feasibility

## Table of Contents

- [Decision](#decision)
- [Cloud-only design](#cloud-only-design)
- [Installer shape](#installer-shape)
- [Security and reliability](#security-and-reliability)
- [Proof of concept](#proof-of-concept)
- [Acceptance criteria](#acceptance-criteria)
- [Sources](#sources)

## Decision

The requested fully cloud-only system is feasible. Python cannot run in Google
Apps Script, so the project now contains a native Apps Script implementation
that reads Gmail, calls the Tricount public-link API, and writes raw JSON plus
attachments into a private Google Drive folder. It runs after installation even
when no computer is online.

## Cloud-only design

```text
Gmail 12-hour trigger
  -> strict subject/body URL detection
  -> Tricount session + registry fetch through UrlFetchApp
  -> Drive title folder with raw JSON, metadata, and attachments
```

The Apps Script scans a bounded Gmail query, then performs a strict local
check before accepting a URL:

1. Query only Inbox messages with `subject:tricount`, in pages, and apply a
   recent-date bound.
2. Confirm the actual message subject contains `tricount` case-insensitively.
3. Read the plain-text body and extract only `https` URLs.
4. Accept a host only when it is exactly `tricount.com` or a subdomain of it;
   do not use a suffix-only test such as `endsWith("tricount.com")`.
5. Parse the public key using the existing URL contract before any API call.
6. Store a record keyed by the normalized public key and Gmail message
   ID, so reruns cannot duplicate imports.

The Drive export is title-based and contains `transactions-<title>.json`,
`tricount-info.json`, and `Attachments <title>/`. It intentionally emits no
CSV. Metadata contains only the share key/URL, message ID, timestamps, and
attachment outcome; it never copies the email body.

`UrlFetchApp` can call HTTPS endpoints, and Drive can create files from text
or blobs. The low expected volume is comfortably below the normal Apps
Script execution model, but each run must page Gmail results and cap the number
of links and attachment downloads to remain inside runtime and fetch quotas.

The open technical risk is the Tricount installation handshake. The current
Python client creates a fresh 2048-bit RSA public key, but Apps Script exposes
RSA signing with a supplied PEM key rather than a documented key-pair generator.
The installer generates a non-secret 2048-bit public PEM, stores it in Script
Properties, and removes its temporary private key before it returns. The
current Python flow never uses its generated private key after authenticating;
the live installation still validates that observation against a real invite.

Attachments look feasible because the existing CLI downloads their URLs with a
plain HTTP GET. The Apps Script variant must save the response as a blob, retain
the original safe filename, record per-attachment failures in metadata, and
never discard the JSON merely because an attachment failed.

## Installer shape

Use a separate `make apps-script-install` target, not `make install`. The
normal install remains self-contained and works after the repository is gone;
the optional target has an interactive Google authorization boundary.

The implemented target:

1. Check Node.js and `@google/clasp` availability; do not install global npm
   packages implicitly.
2. Use an existing private `clasp` authorization, or stop with the one Google
   login command required to establish it. Its linked standard Cloud project
   must enable the Apps Script and Drive APIs.
3. Create a standalone Apps Script project in the user's Google account.
4. Push only the versioned `apps-script/` source and manifest from this repo.
5. Run an installer function once to create the Drive intake folder, configure
   the 12-hour trigger, and report the script and Drive URLs.
6. Keep the generated `.clasp.json`, script ID, and any user-specific folder ID
   outside Git.

`clasp` supports local source management and standalone Apps Script creation,
but Google OAuth consent cannot be silently bypassed. An execution deployment
is used for installer/status calls; the installable trigger runs the script
head directly.

## Security and reliability

| Area | Requirement |
| --- | --- |
| Gmail access | Explicit consent and the narrowest practical read scope. `GmailApp` is simplest but requests broad Gmail access; assess the Advanced Gmail service with a read-only scope before implementation. |
| Drive access | Create a dedicated private folder; do not expose a share link or write into an arbitrary existing folder without an explicit ID. |
| Idempotency | Use `LockService`, a key/message-ID ledger, and atomic metadata updates. Never rely solely on the trigger schedule. |
| URL safety | Parse URLs, require HTTPS, exact `tricount.com` host validation, and normalize the extracted key before any network call. |
| Data minimization | Persist URL/key and Gmail message ID only; never persist the whole email, OAuth tokens, or source mailbox content. |
| Failures | Keep a failed share unprocessed for retry, distinguish fetch versus attachment failures, and emit a concise execution summary. |
| Lifecycle | Provide `apps-script-status` and `apps-script-uninstall`; uninstall removes only this project's managed trigger after explicit confirmation. |

The trigger runs as the account that creates it. Consequently, the installing
Google account must be the mailbox owner and Drive owner intended for exports.

## Proof of concept

Before implementation, validate these two bounded cases with a test email and
a disposable public Tricount link:

1. Gmail detection: confirm the actual invite subject/body format, URL regex,
   canonical key extraction, and idempotent rerun behavior.
2. Cloud API: run the Apps Script session handshake and fetch one registry;
   compare its raw JSON byte-for-byte in structure with the Python response.
3. Attachment path: download one known receipt into the Drive title folder and
   verify a failed receipt leaves the raw JSON and metadata intact.
4. Trigger lifecycle: reconcile exactly one 12-hour trigger and verify the Drive
   layout and collision behavior.

The screenshot of a real invitation should be used only to tune the detector
after redacting the share URL and participant names from fixtures and docs.

## Acceptance criteria

- An optional installer creates one standalone Apps Script project and one
  12-hour installable trigger without changing the normal CLI installation.
- The script processes only valid Tricount share URLs from bounded Inbox
  searches and does not duplicate a key/message combination.
- The cloud-only exporter yields a Drive archive with JSON and attachments,
  without a CSV or a local-computer dependency.
- The Tricount handshake, JSON, attachment retries, quota caps, and Drive
  layout are verified against a real incoming invitation before release.
- The README, installer help, uninstall behavior, OAuth scopes, and tests state
  the same data-flow and permission boundary.

## Sources

- [GmailApp search and message access](https://developers.google.com/apps-script/reference/gmail/gmail-app)
- [Installable time-driven triggers](https://developers.google.com/apps-script/guides/triggers/installable)
- [UrlFetchApp external requests](https://developers.google.com/apps-script/reference/url-fetch/url-fetch-app)
- [Apps Script service quotas](https://developers.google.com/apps-script/guides/services/quotas)
- [DriveApp file creation](https://developers.google.com/apps-script/reference/drive/drive-app)
- [LockService](https://developers.google.com/apps-script/reference/lock/)
- [Utilities RSA support](https://developers.google.com/apps-script/reference/utilities/utilities)
- [Apps Script authorization scopes](https://developers.google.com/apps-script/concepts/scopes)
- [clasp command-line workflow](https://developers.google.com/apps-script/guides/clasp)
