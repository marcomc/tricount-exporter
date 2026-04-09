# TODO

1. Support downloading multiple Tricounts in one run.
2. Preferred CLI shape for multiple keys: allow repeating `--key` multiple times instead of using a comma-separated string.
3. Accept shared Tricount links as input and extract the public key automatically instead of forcing users to extract the key themselves.
4. Preferred CLI shape for shared links: use a repeatable `--url` option rather than a custom positional format.
5. When implementing multi-input runs, allow repeated `--key` and repeated `--url` options in the same command.
6. When implementing multi-key and multi-URL runs, keep each Tricount isolated in its own title-based export folder with the same collision-handling rules already used for single-key exports.
7. Consider optional date-range filtering if Tricount exposes it through the same API.

## Propositions

- [ ] Investigate authenticated account discovery
  - Problem: the current public-link flow works for single Tricount export, but it does not expose a reliable account-wide `user_id` or registry list.
  - Assessment: this is a cross-cutting API-research task with app/network capture dependencies, so it should stay separate from the stable export path until a real authenticated flow is proven.
  - Actions:
    - continue capturing Tricount mobile traffic with Proxyman while keeping `api.tricount.bunq.com` unpinned enough for the app to run
    - look for any authenticated endpoint that returns a stable numeric `user.id` or a registry collection for the logged-in account
    - keep `docs/api-research.md` updated with both positive and negative probes so future work does not repeat the same dead ends
