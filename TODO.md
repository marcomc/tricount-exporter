# TODO
1. Add a dry-run mode that validates the key and shows planned output paths without downloading files.
2. Explore the full Tricount API surface to determine whether a user-scoped identifier can list all Tricounts visible to that user.
3. Investigate how Tricount identifies a user for account-wide discovery and whether the API exposes IDs, memberships, or registries that can be enumerated safely.
4. Support downloading multiple Tricounts in one run.
5. Preferred CLI shape for multiple keys: allow repeating `--key` multiple times instead of using a comma-separated string.
6. Accept shared Tricount links as input and extract the public key automatically instead of forcing users to extract the key themselves.
7. Preferred CLI shape for shared links: use a repeatable `--url` option rather than a custom positional format.
8. When implementing multi-input runs, allow repeated `--key` and repeated `--url` options in the same command.
9. When implementing multi-key and multi-URL runs, keep each Tricount isolated in its own title-based export folder with the same collision-handling rules already used for single-key exports.
10. Consider optional date-range filtering if Tricount exposes it through the same API.
