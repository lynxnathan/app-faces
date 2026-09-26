# Existing catalogs and services

Research date: 2026-09-25. Scope: public first-party documentation for application
artwork sources, delivery, and contributions. No accounts created, uploads made,
services deployed, or provider availability/coverage benchmarks performed.

## Findings

| Candidate | documented capability | Fit for App Faces / limits |
| --- | --- | --- |
| [Dashboard Icons](https://github.com/homarr-labs/dashboard-icons) | Curated application/service/tool icons, SVG/PNG/WebP, direct jsDelivr links; website submissions reviewed and published by admins/contributors. | Closest existing artwork + moderated contribution workflow. Map our application IDs to provider slugs. An API for third-party client submissions is unverified. |
| [selfh.st/icons](https://github.com/selfhst/icons) | Software icon collection, JSON indexes, jsDelivr delivery, multiple formats; repository labeled CC BY 4.0. Requests go through discussions; outside contributors' PRs are not accepted. | Strong additional provider; indexed assets can seed mappings. Does not document our executable fingerprint matching or direct client uploads. |
| [Flathub / AppStream](https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines) | AppStream catalogs combine application metadata, desktop launchables, and generated icons; used by GNOME Software and KDE Discover. | Strong source of desktop application identity. Evaluate existing local catalogs first. A raw executable still needs a reliable association to the component; this is not a universal binary-hash API. |
| [Iconify](https://iconify.design/docs/api/) | Public API for searching/browsing icon sets, retrieving data, and rendering SVG; supports multiple providers and self-hosting. | Useful secondary artwork search/delivery option. Collection and asset provenance matter; an arbitrary search hit is not an application identity match. |
| [FaviconAPI](https://www.faviconapi.com/docs/getting-started) | Self-hostable aggregator for website favicons and service icons from catalogs including selfh.st and Dashboard Icons; caching and normalized PNG output. | Possible delivery adapter, not required for the MVP. Service-name lookup is documented; binary matching and our moderation workflow are not established. |

Dashboard Icons already has much of the proposed community review
shape. Its [web implementation notes](https://github.com/homarr-labs/dashboard-icons/blob/main/web/README.md)
also document external provider metadata with artwork remaining upstream, a useful
reference for keeping identity mappings separate from asset hosting.

provider documentation and licensing references:

- [Dashboard Icons license](https://github.com/homarr-labs/dashboard-icons/blob/main/LICENSE)
  and README legal section: preserve asset provenance and third-party notices;
  do not treat a repository software license as a blanket license for every logo.
- [selfh.st collection and license](https://github.com/selfhst/icons) and
  [CDN usage](https://selfh.st/icons-about/).
- [Iconify collections and their individual licenses](https://github.com/iconify/icon-sets/blob/master/collections.md).
- [FaviconAPI endpoints](https://faviconapi.com/docs/api).

## Accepted direction and implementation recommendation

after reviewing the findings, Nathan confirmed “we will reuse those”.
The remaining evaluation selects adapters and measures coverage; it does not
reopen whether to start by building a duplicate artwork CDN.

Start with desktop entries, bundled icons, and locally available AppStream data.
For unresolved artwork, use provider adapters with explicit application-ID-to-slug
mappings, beginning with Dashboard Icons and selfh.st. Keep our catalog small:
identity evidence, aliases, fingerprint rules, provider references, and exceptions.

Download versioned metadata for local matching and cache selected artwork. Remote
asset downloads still reveal the requested asset and connection metadata to the
provider; local matching does not mean zero network disclosure. Do not upload
paths, raw desktop entries, launch arguments, or binary hashes as a side effect.

Reuse an existing contribution route where practical. Retain Nathan's Cloudflare
submission backend as the fallback for missing coverage, custom variants, or a
review experience that cannot be integrated with an existing provider. The
moderated submission workflow remains in scope even if most artwork stays on
someone else's CDN. Contributions are anonymous and throttled, with no contributor
login or identity tracking (Nathan's clarification). Authentication is
for reviewers, not contributors. Asset provenance means where artwork originated
and its attribution/license, not the identity of the person uploading it.

## What is not established

unverified — no reviewed provider documents the entire combination of arbitrary
Linux executable recognition, desktop-entry precedence, local matching, native
Files integration, and opt-in client submissions moderated by Nathan. This is a
bounded research finding, not proof that no such project exists.

unverified — application coverage for Nathan's collection; public submission API
availability; production rate limits and caching terms; long-term service
availability; rights for individual submitted or imported assets.

## Provider evaluation before implementation

- Choose a representative set of 20–30 apps with common, obscure, proprietary,
  renamed, and versioned examples; record identity match separately from artwork
  availability and preferred desktop artwork versus a generic brand logo.
- Record source revision, asset URL, digest, dimensions, variant, license, and
  attribution. Prefer pinned revisions for reproducibility where supported.
- Check caching/redistribution conditions and endpoint behavior before integration.
- Measure overlap and missing coverage; avoid building a duplicate full catalog.
- Evaluate whether an existing moderated submission system can be reused without
  requiring unapproved automated posts or scraping private APIs.
- Choose hosted provider versus our own backend based on the measured gaps.
