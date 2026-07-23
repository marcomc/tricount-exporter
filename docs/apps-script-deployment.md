# Google Apps Script deployment

## Table of Contents

- [Development source](#development-source)
- [Remote lifecycle](#remote-lifecycle)
- [Release boundary](#release-boundary)

## Development source

The versioned cloud source lives in `apps-script/`. It is copied into ignored
private installer state before `clasp` creates or updates a standalone script.
The generated `.clasp.json` therefore never belongs in the repository.

## Remote lifecycle

`make apps-script-install` performs these ordered steps:

1. Validate local tools and Apps Script JavaScript syntax.
2. Copy source and inject the configured IANA timezone into the staged manifest.
3. Obtain a private owner authorization from the Desktop OAuth client in the
   linked standard Cloud project, where the Apps Script and Drive APIs are
   enabled.
4. Create the remote standalone project if absent, then push its source.
5. Create or update the owner-only execution deployment.
6. Generate a temporary RSA keypair and bootstrap Script Properties, Drive, and
   the 12-hour trigger through the remote script.

The execution deployment is for installer/status calls. The 12-hour installable
trigger runs the Apps Script project head; it is not a versioned web service.

## Release boundary

Do not push source, deploy a stable version, or alter triggers merely because a
local branch changed. Validate with `make check`, then explicitly authorize the
remote deployment operation. The installer is idempotent for its own project
mapping and does not touch unrelated Apps Script projects.
