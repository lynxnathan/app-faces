# Test quality

Tests assert outcomes: selected artwork, persisted state, preserved user changes,
rejected inputs and recoverable failures. Test totals include parameterized cases;
ten language cases are not ten distinct features.

## Assertion audit — 26 September 2026

| Area | Defect in the previous check | Current assertion |
| --- | --- | --- |
| Bundle ambiguity | Missing artwork masked removal of ambiguity rejection | Two otherwise valid entries are rejected; removing one restores successful extraction |
| Candidate execution | Missing extraction directory did not prove the candidate was never started | Subprocess boundary rejects candidate execution and shell invocation while real archive reads complete |
| AppStream traversal | A nonexistent escape target could pass without traversal protection | Separate origin and filename escapes point to existing artwork and remain unresolved |
| Fingerprint cache | Equal hashes did not prove cache reuse | Binary reads are counted; unchanged files are not reread and changed bytes produce the expected hash |
| Upload privacy | Column names did not prove absence of stored IPs | All application D1 rows are inspected for the test raw IP; ten accepted uploads are persisted |
| Moderation access | A `textContent` string did not prove authorization | Anonymous and invalid credentials are rejected on queue, reviews and private image endpoints |
| Backend isolation | Merge depended on an earlier test's published application | Every case gets fresh Worker/D1 state and creates required records; shuffled execution passes |
| Native Apply | Any application call satisfied the assertion | Exact target, selected artwork and replacement option are checked despite sharing failure |
| KDE bridge | Source strings stood in for runtime protection | Compiled plugin returns expected pixels, rejects remote/missing inputs, and leaves candidate/shell execution markers absent |

## Targeted mutation checks

```sh
npm --prefix backend run build
uv run --frozen python tests/mutations.py
```

Requires the regular Python test environment, SquashFS tools, Node and installed
backend development dependencies. Each check first runs its unchanged test, then
introduces one deliberate defect in a child process or temporary source copy.
The runner requires an assertion failure, rather than counting a setup error as
success. It never modifies production source files in the checkout.

The six mutations remove bundle ambiguity rejection, attempt candidate execution,
remove each AppStream traversal guard, bypass fingerprint cache reuse, and persist
the upload IP in a D1 field. Evidence is saved in ignored
`state/test-mutations.json`. These are targeted regression checks, not an exhaustive
mutation score.

## Boundaries

- D1 privacy checks cover raw IP storage in application tables, not Cloudflare's
  internal tables, infrastructure logs or every possible encoding of an address.
- KDE metadata checks validate registration/cache settings. The compiled CTest
  validates the plugin/helper boundary; it does not replace the live Dolphin flow.
  Helper timeout behavior is not exercised by that CTest.
- GTK component checks mock selected external operations. Real file-manager and
  dock flows have separate runners and environment requirements.
- Language tests check catalog completeness, interpolation, RTL and usable flows.
  They do not judge translation wording. Screenshots alone are not visual assertions.
- The browser suite was unchanged in this audit; its earlier 20 passing scenarios
  are recorded separately in the review document.
