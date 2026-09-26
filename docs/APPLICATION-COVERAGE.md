# Real application coverage — 26 September 2026

`state/application-coverage.json`, `state/application-coverage-after-local-seed.json`, and `state/occt-local-seed.json`, generated in Nathan's real graphical user session.

The benchmark selects 24 installed desktop entries by lowest SHA-256 ordering of their desktop IDs, excluding `NoDisplay` entries, then adds the actual `Downloads/OCCT` file. Selection happens before resolution, keeps wrappers and ambiguous entries, and does not replace failures with hand-picked successes. It is reproducible for the same installed entries. It reads files and installed metadata, never launches a sampled app, sends no network requests, and changes no file icons. Its only persistent write is its selected JSON report. OCCT's SHA-256 comparison remains local; the report contains no executable hash.

| Installed desktop sample | Result |
| --- | ---: |
| Exact executable → unique desktop identity | 15 / 24 |
| Ambiguous executable shared by multiple desktop entries | 7 / 24 |
| Unsupported wrapper launch commands | 2 / 24 |
| Declared desktop artwork exists locally | 23 / 24 |
| Artwork available through unambiguous resolver result | 14 / 24 |

These measure different things. An icon existing for a desktop entry does not establish which entry a loose executable should use. Likewise, a resolved identity with a missing theme asset is not an artwork success. Existing `.desktop` declarations remain authoritative; the benchmark does not silently override an ambiguity. This is one-machine integration coverage, not an estimated worldwide match rate, an E2E UI flow, or proof that GNOME Dock/Dolphin display it. Installed applications dominate the sample; portable coverage is only OCCT.

## OCCT: explicit local knowledge, not universal recognition

Baseline OCCT resolution is unknown. The executable exactly matches the earlier local user-identified OCCT evidence. With Nathan's instruction to finish local recognition, `scripts/seed_local_application.py` now preserves the previous catalog revision and adds a **user-local exact-build** fingerprint record. The artwork is the already downloaded official-site favicon (`https://www.ocbase.com/favicon.ico`), normalized into local managed storage. The mapping carries source, local evidence, exact-build scope, and `unknown; local use only; no redistribution authorized` license metadata.

After seeding, explicit fingerprint resolution returns `resolved / sha256 / OCCT` with available local artwork. Ordinary resolution without fingerprinting still returns unknown; the after-seed report preserves this distinction. No universal OCCT rule, version claim, publisher checksum verification, artwork distribution, or community upload was added. Neither seeding nor this benchmark calls icon application. The existing automatic scanner may subsequently consume the mapping when fingerprint scanning is enabled, subject to its user-choice/undo rules.

The seed refuses changed bytes or an existing fingerprint mapping. It retains all existing icons and fingerprints. To remove this mapping and restore the previous catalog:

```sh
app-faces catalog --revision e1209d6d5c04b7b9633e60661c0c73fd9002b3486abe87d1cdc8fd674edd738c
```

This restores recognition metadata. An icon already applied by the background scanner is separately reversible through the existing Undo/rollback flow. Future user catalog edits should not be discarded blindly by restoring an older revision.

## Reproduce

From the project directory in the graphical user session:

```sh
PYTHONPATH=. /usr/bin/python3 tests/integration/application_coverage.py --output state/application-coverage-latest.json
```

Five targeted tests cover stable selection with unresolved launchers retained, independent identity/artwork accounting, changed-build refusal, and preservation of an existing user mapping. Strict type checking passes for both scripts. Further coverage should add real portable applications from known sources rather than manufacturing successes from synthetic hashes.
