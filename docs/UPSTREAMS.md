# Adding an upstream or fork

[source configuration/adapters](../app_faces/upstreams.py),
[resolver and downloads](../app_faces/core.py), [tests](../tests/test_upstreams.py),
and configured-source native E2E (`../state/native-e2e/configured-selfhst-mirror/upstream-result.json`, local).

A GitHub fork that keeps either supported collection format needs configuration,
not a code change. Contributor login and our Cloudflare backend are not involved
in downloading these public collections.

## Configure a source

Create `~/.config/app-faces/upstreams.toml` (or
`$XDG_CONFIG_HOME/app-faces/upstreams.toml` when XDG_CONFIG_HOME is set):

```toml
[[sources]]
id = "my-icons"
repository = "OWNER/REPOSITORY"
format = "selfhst"
ref = "main"
enabled = true
priority = 50
```

Replace OWNER/REPOSITORY with the public GitHub repository. Use `format = "dashboard"`
for the Dashboard Icons schema. Each repository must provide the chosen metadata
format and `png/SLUG.png` artwork. Arbitrary hosting services and custom asset URL
layouts are not supported by this first implementation.

The defaults remain enabled unless overridden: `selfhst` uses `selfhst/icons`
at priority 100; `dashboard` uses `homarr-labs/dashboard-icons` at priority 200.
To disable a default without copying all its fields:

```toml
[[sources]]
id = "dashboard"
enabled = false
```

`id` is the stable local source namespace; do not reuse it for unrelated sources.
`ref` accepts a branch, tag or lowercase 40-character commit SHA. A mutable ref is
resolved once per sync; metadata and artwork use that immutable commit. A fixed
SHA avoids the revision API request. `priority` is an integer from 0 to 10000;
lower numbers sort suggestions first, with source ID breaking ties. It does not
increase recognition confidence or override existing manual icons.

```sh
app-faces sources                    # validate and inspect effective sources
app-faces sync                       # explicitly refresh now, if desired
app-faces search telegram
```

Configuration changes trigger refresh on the next normal background scan, even
when the previous catalog is fresh. Unchanged configuration (including comments or
whitespace edits) does not trigger repeat downloads. These are maintenance commands,
not a required “Load” workflow for users choosing icons. Failed refreshes back off
15 minutes for the same configuration; an edited configuration can retry immediately.
Source policy changes also invalidate cached recognition results. Invalid configuration
reports a diagnostic and skips network/application safely until corrected.

## Disable, remove, failure and rollback

Set `enabled = false` to stop using a source. Delete a custom source's TOML entry
to remove it; deleting a default override restores that default. Disabled/removed
sources disappear from suggestions without deleting icons already applied to files,
cached artwork or historical snapshots. Re-enable/re-add the source to expose its
records again. An explicit pinned artwork request can still use a valid local cache
after disabling/removing the source; new downloads from it are refused.

If one enabled source fails, synchronization reports the error, retains its previous
records and updates the healthy sources. If every enabled source fails, the working
snapshot is left untouched. Invalid configuration fails before replacing a snapshot.
Configuration is bounded to 64 KiB and 32 declared sources; duplicate IDs, unknown
fields/formats, malformed repositories/references and invalid priorities are rejected.

Catalog snapshots retain repository, revision, source URL and content provenance.
Rollback does not require the old repository to remain in current configuration.
Source filtering still applies: restoring a snapshot does not silently re-enable a
source the user disabled. Use the existing `app-faces catalog --revision REVISION`
operation for snapshot rollback. Collection provenance does not establish individual
artwork licenses; those continue to be marked unknown until separately established.

## Add a different metadata format

The `ADAPTERS` registry maps a format name to its metadata filename and a parser
returning `(slug, display_name)` pairs. Existing selfh.st and Dashboard parsers are
separate functions. A new adapter must validate the document structure and emit
normalized records; common processing validates identifiers/names, rejects
conflicting duplicate slugs and handles pinning, bounded downloads, image
normalization, caching and catalog rollback.

This registry is application code, not an arbitrary executable plugin loaded from
TOML. Custom PNG locations or non-GitHub hosting require extending the common asset
transport contract as well; they cannot be accomplished by adding a metadata parser
alone. Tests include a third test-only format to verify the adapter boundary.

## What the actual configured-source E2E proves

[tests/integration/e2e-configured-upstream.sh](../tests/integration/e2e-configured-upstream.sh) declares
`selfhst-mirror` solely in a temporary TOML file, disables the built-in sources and
syncs a pinned revision. It points at the existing selfh.st repository under a new
source ID; it does **not** create a GitHub fork or claim to test a third-party fork.
It exercises the same configuration path a compatible fork uses.

The saved run then starts with no artwork cache, opens real Nautilus/GTK on private
Xvfb, selects Telegram from that configured source, cancels without modifying the
file, reopens, downloads/applies the icon, verifies its rendered shape in Files and
restores the generic icon with Undo. No folder reload, executable launch, upload or
personal source configuration change occurs. The misleading-name control remains
untouched by automation. Unit/integration cases additionally cover source outages,
duplicate slugs, disabled/removed sources, malformed metadata, missing artwork,
offline cached artwork and rollback.
