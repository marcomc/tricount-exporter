# TODO

## Next

1. Remove the retrocompatibility layer because this fork is now a full rewrite rather than a drop-in continuation of the upstream project.
2. Reduce the codebase to the minimal maintained surface needed for this fork and remove inherited compatibility behavior that no longer serves the rewritten project.
3. Add explicit attribution in the README and license materials to the original upstream author while stating that this fork is now a complete rewrite from the original base.
4. Improve code quality automation so Python gets the same kind of enforceable quality gate that ShellCheck gives shell code.
5. Add Python quality tools to the `make`-driven regression workflow so style, static checks, and test execution run together in a repeatable way.
6. Expand regression tests to cover config loading and export path behavior as the codebase changes.
7. Add a dry-run mode that validates the key and shows planned output paths without downloading files.
8. Explore the full Tricount API surface to determine whether a user-scoped identifier can list all Tricounts visible to that user.
9. Investigate how Tricount identifies a user for account-wide discovery and whether the API exposes IDs, memberships, or registries that can be enumerated safely.
10. Support downloading multiple Tricounts in one run.
11. Preferred CLI shape for multiple keys: allow repeating `--key` multiple times instead of using a comma-separated string.
12. Accept shared Tricount links as input and extract the public key automatically instead of forcing users to extract the key themselves.
13. Preferred CLI shape for shared links: use a repeatable `--url` option rather than a custom positional format.
14. When implementing multi-input runs, allow repeated `--key` and repeated `--url` options in the same command.
15. When implementing multi-key and multi-URL runs, keep each Tricount isolated in its own title-based export folder with the same collision-handling rules already used for single-key exports.
16. Consider optional date-range filtering if Tricount exposes it through the same API.
17. Choose a new project name before creating the standalone GitHub repository.
18. Detach this fork operationally from the original GitHub repository and publish it as a new standalone repository.
