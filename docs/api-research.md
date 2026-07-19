# API Research

## Table of Contents

- [Scope](#scope)
- [Current Authentication Flow](#current-authentication-flow)
- [Observed Session Payload](#observed-session-payload)
- [Registry Endpoints](#registry-endpoints)
- [Findings For Account-Wide Discovery](#findings-for-account-wide-discovery)
- [Mobile Capture Follow-up](#mobile-capture-follow-up)
- [Developer Notes](#developer-notes)

## Scope

This document records the current Tricount API findings used by
`tricount-exporter`.

The findings below come from:

- the live behavior of the current CLI implementation
- direct probe requests performed on `2026-04-09`

No private user credentials were used for this research. The scope was limited
to the anonymous public-link flow used by the project itself.

## Current Authentication Flow

The current client flow is:

1. Generate a random `app_installation_id` UUID.
2. Generate a fresh RSA keypair locally.
3. `POST /v1/session-registry-installation`
4. Extract:
   - `Token.token`
   - `UserPerson.id`
5. Use `X-Bunq-Client-Authentication` with that token for subsequent requests.
6. Fetch a specific Tricount with
   `GET /v1/user/<user_id>/registry?public_identifier_token=<shared-key>`.

Base URL:

```text
https://api.tricount.bunq.com
```

Headers currently used:

```text
User-Agent: com.bunq.tricount.android:RELEASE:7.0.7:3174:ANDROID:13:C
app-id: <generated uuid>
X-Bunq-Client-Request-Id: 049bfcdf-6ae4-4cee-af7b-45da31ea85d0
X-Bunq-Client-Authentication: <session token>
```

## Observed Session Payload

The installation endpoint returns a mixed `Response` array that includes at
least:

- `Id`
- `Token`
- `EncryptionKey`
- `UserPerson`

Important observed details:

- the endpoint rejects RSA keys with the wrong modulus length
- a `1024`-bit key was rejected with:
  `Provided client public key has an incorrect modulus length. Modulus length must be "2048", got "1024"`
- a `2048`-bit key succeeded

The returned `UserPerson` for the anonymous flow looked like a generated
participant account rather than an authenticated personal account. Observed
fields included:

- `status: SIGNUP`
- `display_name: tricount participant`
- `public_nick_name: tricount participant`

This strongly suggests that the public-link flow creates or reuses an anonymous
participant context, not a fully authenticated end-user session.

## Registry Endpoints

Observed endpoints:

### `GET /v1/user/<user_id>/registry?public_identifier_token=<key>`

Current use in the application.

Purpose:

- fetch one Tricount registry by shared public key

Observed response shape assumptions used by the exporter:

- `Response[0]["Registry"]["title"]`
- `Registry["memberships"]`
- `Registry["all_registry_entry"]`
- `RegistryEntry["allocations"]`
- `attachment["urls"][0]["url"]`

### `GET /v1/user/<user_id>/registry`

Observed behavior during live probes:

- returns `200`
- returns an empty `Response` array in the anonymous public-link session

Example shape:

```json
{
  "Response": [],
  "Pagination": {
    "future_url": null,
    "newer_url": null,
    "older_url": null
  }
}
```

### `GET /v1/user/<user_id>/registry?count=10`

Observed behavior:

- same as above for the anonymous session
- `200` with an empty `Response` array

### `GET /v1/user/<user_id>/registry?public_identifier_token=`

Observed behavior:

- also `200` with an empty `Response` array

### `GET /v1/user/<user_id>/registry-membership`

Observed behavior:

- `404 Route not found`

## Findings For Account-Wide Discovery

Current conclusion:

- there is evidence that a user-scoped registry collection endpoint exists:
  `GET /v1/user/<user_id>/registry`
- there is not yet evidence that the public-link authentication flow used by
  `tricount-exporter` can enumerate a real person’s Tricounts
- in the anonymous session observed during this research, the registry list
  endpoint returned an empty list

What this means for TODO items 2 and 3:

- the API shape suggests that account-wide listing may exist for a different
  class of authenticated user
- the current public-link flow does not provide enough evidence to implement
  account-wide discovery safely
- the `user_id` obtained from `session-registry-installation` should currently
  be treated as an anonymous session-scoped participant identity, not as proof
  of a recoverable personal account identity

At this stage, there is no safe implementation path for "list all Tricounts for
a user" without further research into authenticated account sessions beyond the
public-link flow.

## Mobile Capture Follow-up

The later iPhone capture session added a few more concrete findings:

- enabling SSL proxying for `api.tricount.bunq.com` caused the app to fail
  with a server-trust error
- disabling SSL proxying for that host allowed the app to log in and continue
  running
- Proxyman could then observe `CONNECT` tunnels to `api.tricount.bunq.com`,
  `sentry.bunq.com`, and `snowplow-tricount.data.bunq.com`
- the login/session telemetry exposed a UUID-shaped analytics `userId`
  (`a42013ff-9000-4652-b3f6-ad57a5d3bc00`), but that value did not work as a
  Tricount API `user_id`
- a numeric candidate from the capture (`92124206`) also failed when used as
  `/v1/user/<id>/registry`
- a fresh anonymous API session created during direct probing returned a
  separate numeric `UserPerson.id` (`79939318`), but that session still did not
  enumerate any registries and should not be treated as proof of a recoverable
  personal account identity

This means the current research state is:

- the app can log in and reach the live Tricount API
- the app still does not expose a confirmed account-wide user identifier
- the API payloads remain opaque while the app is protected by trust checks or
  when SSL proxying is disabled for the real API host
- more research is needed before any account-wide listing feature can be wired
  into the CLI

## Developer Notes

Current implementation file:

- [`src/tricount_exporter/cli.py`](../src/tricount_exporter/cli.py)

If future work revisits account-wide discovery:

- keep the research separate from the stable public-link export flow
- avoid shipping speculative endpoints without regression coverage
- document any newly observed authenticated flows before wiring them into the
  CLI
