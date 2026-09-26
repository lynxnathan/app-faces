# Sources and verification

Use this page to trace a behavior to its specification, implementation and tests.
Local execution reports and screenshots are not shipped; the test runners are.

## Desktop integration

| Behavior | Reference | Implementation and checks |
| --- | --- | --- |
| Read `.desktop` entries and respect user overrides | [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry/latest-single/) | [Resolver](app_faces/core.py), [resolver tests](tests/test_resolver.py) |
| Resolve named icons through installed themes | [Icon Theme Specification](https://specifications.freedesktop.org/icon-theme/) | [Resolver](app_faces/core.py), [resolver tests](tests/test_resolver.py) |
| Associate launchers with application windows | [GNOME application IDs](https://developer.gnome.org/documentation/tutorials/application-id.html), [GNOME integration](https://developer.gnome.org/documentation/guidelines/maintainer/integrating.html) | [Launchers](app_faces/launchers.py), [dock flow](docs/DOCK-E2E.md) |
| Read embedded AppImage icons without executing the app | [AppDir layout](https://docs.appimage.org/reference/appdir.html), [ELF sections](https://gabi.xinuos.com/v42/elf/03-sheader.html) | [Bounded reader](app_faces/bundles.py), [archive tests](tests/test_bundles.py) |
| Apply file icons and undo owned changes | [GNOME custom-icon discussion](https://discourse.gnome.org/t/use-xattr-to-set-custom-icon/34578) | [State journal](app_faces/state.py), [state tests](tests/test_state.py), [real-file lifecycle](tests/integration/file-lifecycle-e2e.py) |

File-manager icons and running-window association are separate behaviors. A valid
`.desktop` entry does not prove dock grouping. See [dock verification](docs/DOCK-E2E.md)
for the observed Wayland and XWayland identities and test boundaries.

## Catalogs and contributions

- [Catalog research](docs/CATALOG-RESEARCH.md) records the provider and licensing references.
- [Source configuration](docs/UPSTREAMS.md) documents adapters, forks and cache behavior.
- [Contribution protocol](backend/CONTRIBUTIONS.md) defines consent, receipts and moderation.
- [Moderation flows](docs/MODERATION-FLOWS.md) maps states to checks and lists coverage limits.
- [Deployment](docs/DEPLOYMENT.md) records the Cloudflare configuration and deployment history.

## Reproduce the checks

[Development](DEVELOPMENT.md) contains setup and test commands.
[Review](docs/REVIEW.md) and the [roadmap](ROADMAP.md) record completed work and its limits.
[Language checks](docs/I18N.md) cover catalog completeness, parameter preservation,
locale selection, direction and interface flows. These checks do not constitute
native-speaker review of every translation.

Machine-specific reports live in ignored `state/`. Their existence is not a
substitute for a reproducible test, and a historical passing run is not a claim
that every environment or future version will pass.

[Assertion audit](docs/TEST-QUALITY.md) records test weaknesses corrected and reproducible mutation checks.
