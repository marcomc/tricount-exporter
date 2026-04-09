# TODO

1. Support downloading multiple Tricounts in one run.
2. Preferred CLI shape for multiple keys: allow repeating `--key` multiple times instead of using a comma-separated string.
3. Accept shared Tricount links as input and extract the public key automatically instead of forcing users to extract the key themselves.
4. Preferred CLI shape for shared links: use a repeatable `--url` option rather than a custom positional format.
5. When implementing multi-input runs, allow repeated `--key` and repeated `--url` options in the same command.
6. When implementing multi-key and multi-URL runs, keep each Tricount isolated in its own title-based export folder with the same collision-handling rules already used for single-key exports.
7. Consider optional date-range filtering if Tricount exposes it through the same API.
