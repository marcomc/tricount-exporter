# TODO

## Propositions

- [ ] Complete a disposable Google Apps Script integration test
  - Use a test Gmail invitation and public Tricount share URL.
  - Verify the real API handshake, Drive JSON, attachment failure handling,
    12-hour trigger reconciliation, and duplicate suppression.

- [ ] Add a read-only Apps Script reconciliation command
  - Compare the local installer state, remote script, trigger count, Drive
    root, and Script Properties without changing Google resources.

- [ ] Investigate authenticated account discovery
  - Problem: the current public-link flow works for single Tricount export, but it does not expose a reliable account-wide `user_id` or registry list.
  - Assessment: this is a cross-cutting API-research task with app/network capture dependencies, so it should stay separate from the stable export path until a real authenticated flow is proven.
  - Actions:
    - continue capturing Tricount mobile traffic with Proxyman while keeping `api.tricount.bunq.com` unpinned enough for the app to run
    - look for any authenticated endpoint that returns a stable numeric `user.id` or a registry collection for the logged-in account
    - keep `docs/api-research.md` updated with both positive and negative probes so future work does not repeat the same dead ends
