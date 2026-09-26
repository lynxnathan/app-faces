# App Faces

- Use English for code, identifiers, tests, documentation and commit messages.
- Keep translated interface text in locale catalogs. Support en, zh, hi, es, fr, ar, bn, pt, ru and ur.
- Keep the README concise: features, requirements and installation commands.
- Avoid code comments unless a specific non-obvious constraint requires one. Keep explanations in documentation.
- Name behavioral limits, timeouts, thresholds and tolerances. Do not extract ordinary zero/one values or layout dimensions without a useful name.
- Keep the repository history as a single root commit until Nathan says “ok released”. Amend that commit and push with an explicit force-with-lease against the previously observed remote commit.
- Keep screenshots, execution reports, credentials and desktop session data local.
- Run changes and Git operations as lynxnathan. Never log out or reboot the desktop.

- Maintain provenance in versioned `SOURCES.md` with links to specifications, implementation and tests. Do not prefix prose with audit labels. Raw execution evidence stays in ignored `state/`.

- Tests must assert observable behavior and isolate each failure condition. Check persisted state and unchanged user data where relevant. Use targeted mutations to verify critical assertions; do not use source-text presence as proof of runtime behavior. Test cases must create their own required state.

- Keep test artwork and sample applications in `tests/fixtures/`, desktop runners in `tests/integration/`, and KDE-specific tests in `adapters/kde/tests/`. Build outputs stay ignored. Application-specific observations belong in verification records, not runtime defaults.
