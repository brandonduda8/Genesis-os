# RECEIPT — GHOST-Q-015 Phase 2: Watch+Pulse v1 APK Build

**Date:** 2026-10-31 (~17:48–17:56 UTC)
**Phase:** P2_build_v1 (GHOST-Q-015 Watch+Pulse)
**Verdict: BUILT-UNVERIFIED** — the APK compiled, signed with the new stable
release key, and passed `apksigner verify` + `zipalign -c` on this box.
It has NOT been installed on a device yet; P3 verification (feature pass on
Brandon's phone) and P4 (in Brandon's hands) remain.

## Deliverable

- **APK:** `/home/hatch/workspace/genesis-os/watch-pulse/builds/watch-pulse-v1.apk`
- **Size:** 70,834 bytes
- **SHA-256:** `c82cdb0966b90a73d73f0d2903a69e28576c05226ca90a98b6fe2f3b6f9901e1`
- **Rebuild note:** the APK was built twice pre-delivery under the same key —
  first with a synthesized fallback catalog (54,450 B, sha256 b76e566c…),
  then rebuilt the same hour after a late find surfaced the real catalog
  (below). Only the second build was ever copied to the deliverable path;
  v1 never shipped in between.
- **Package:** `com.genesis.watchpulse` · versionCode 1 · versionName 1.0 ·
  minSdk 24 · targetSdk 34 · permissions: INTERNET, ACCESS_NETWORK_STATE only
- **Project:** `~/workspace/.android-build/watchpulse/` (sources, assets,
  `apksigner-verify.txt` preserved)

## Signing identity (stable — v2+ installs over v1)

- **Keystore:** `/home/hatch/workspace/.android-build/watchpulse-release.keystore`
  (RSA 4096, alias `watchpulse`, validity 10,000 days, chmod 600)
- **Password:** stored ONLY in
  `/home/hatch/workspace/.android-build/watchpulse-release.pass` (chmod 600;
  two identical lines — apksigner's `file:` reader consumes keystore and key
  passwords sequentially from the same file). Never printed, never in this
  receipt.
- **Signer cert DN:** CN=Genesis WatchPulse, O=Genesis, C=US
- **Signer cert SHA-256:** `20224a4e8c7b803798b812be94bd265b3d0bed1d6cc936b2c179790e9619b953`
- **Signer cert SHA-1:** `d81a4fd53befd62577067a2dbab5def7105702ed`

**apksigner verify --print-certs (verbatim):**

```
Signer #1 certificate DN: CN=Genesis WatchPulse, O=Genesis, C=US
Signer #1 certificate SHA-256 digest: 20224a4e8c7b803798b812be94bd265b3d0bed1d6cc936b2c179790e9619b953
Signer #1 certificate SHA-1 digest: d81a4fd53befd62577067a2dbab5def7105702ed
Signer #1 certificate MD5 digest: a362416c4ec0ae7c61a79f6f5bce54bc
```

(Verify exited 0. zipalign -c also passed.)

## Aurum source bundled (PULSE zone)

Source hunt outcome, honestly: the Aurum 2.1 APK is a native Kotlin/Compose
app (44 MB dex) with no web player inside — its `assets/tracks.json` is a
54-byte empty stub, and the `genesis-player` source copy of the catalog is
the same empty stub. The most complete Aurum **web** player on disk is the
workshop build, bundled instead:

- **Player:** `~/workspace/workshop/static/aurum.html` (42,102 bytes,
  2026-10-01 build — search, tabs, albums, For You, shuffle/resume,
  MediaSession, Apollo chat UI) → `assets/aurum/index.html`
- **Plus:** `aurum.webmanifest`, `aurum-icon-192.png`, `aurum-icon-512.png`
  from the same static dir.
- **Catalog:** Brandon's real Aurum library, transformed into the player's
  native `/api/aurum/tracks` format (`{tracks, playlists, for_you}`) →
  `assets/aurum/tracks.json` (145,702 bytes):
  - Source of record: `music-lane/catalog-444-backup-20261005.json` —
    catalog **v10** (generated 2026-10-04), 444 tracks. It stores
    `audius_stream_url` per track; the transform maps it to the player's
    `stream_url`, extracts the Audius track id from the URL, and carries
    artwork + playlist memberships across unchanged.
  - **385 tracks bundled** (the 382 Audius-streaming library tracks + the
    3 Audius entries of the RAGE remote set,
    `music-lane/catalog.remote.json`, merged by id with the RAGE tag) —
    284 artists, **224 with real artwork**, and **13 of Brandon's actual
    playlists** as tabs: Full Blend, RAGE, Peep Forever, Cloud Nine,
    Deep Poetry Trap, Apollo Hunt, Loved, Legends, Sad Boy, Phoenix
    Rising, Dark Cinematic, Night Drive, Underground Heat.
  - For You (30): the catalog's own reasoned picks + Loved playlist +
    Apollo Hunt selections, with reasons.
  - An earlier fallback synthesis (185 Apollo-candidate tracks) was built
    first and discarded before delivery once v10 surfaced — the shipped
    bundle is the real library, not the candidate list.
- **Serving model:** the WebView loads `https://aurum.watchpulse.local/aurum`;
  a WebViewClient intercepts that origin and serves the bundled page,
  manifest, icons, and catalog from assets — so shell + library load fully
  offline. Streams/artwork use the network when available (per design note).

## Feature checklist vs design note + P2 spec

| Item | State |
|---|---|
| Quantum Void shell (deep-purple bg, purple zone tiles) | DONE — home + all zones styled, gold reserved |
| "GENESIS" title + breathing Pulse dot | DONE — gold dot, handler-driven alpha/scale breath |
| Zone tiles PULSE / WATCH / BUILD / FLEET / FORGE | DONE — all five on home |
| PULSE: Aurum in a WebView, assets local | DONE — player + real 385-track catalog (v10) bundled; JS + media playback + DOM storage (resume) enabled |
| WATCH (Shape A): designed tile list | DONE — Your Playlists, Subscriptions, History, Watch Later, YouTube Home |
| WATCH: ACTION_VIEW → official YouTube app, browser fallback | DONE — intents pinned to `com.google.android.youtube`; playlists row uses `https://www.youtube.com/feed/playlists`; ActivityNotFoundException falls back to a plain view intent |
| No credential handling / no embedded YT player / no unofficial APIs | DONE — none present |
| BUILD / FLEET / FORGE honest placeholders | DONE — dimmed tiles opening a screen that says the zone docks in a later build |
| Manual pipeline only, SDK android.jar deps only | DONE — aapt2 → javac → d8 → zipalign → apksigner; no Gradle, no network fetches |
| Signed with stable release key + apksigner verify | DONE — see identity above |

## Honest placeholders & limits (v1)

- **BUILD / FLEET / FORGE** are design-language placeholders, labeled as such
  in-app. No functionality behind them.
- **SoundCloud-only tracks are NOT in the bundled catalog:** 62 of the 444
  library tracks (including the entire Tha Aadity and Ghostlands playlists)
  and 29 of the 32 RAGE remote tracks carry only SoundCloud page URLs.
  Their playable form needs the workshop's server-side
  `/api/aurum/scstream` resolver (signed-media refresh); page URLs alone
  don't play. Path to fix in v2: bundle transcoding endpoints + an in-app
  resolver, or re-source them on Audius.
- **Apollo chat** inside Pulse is stubbed: the bundled player POSTs to
  `/api/aurum/chat`, which the shell answers with a fixed, honest reply
  (chat lives on the live workshop) + `brain:"fallback"`, which the player
  itself labels as local-fallback mode.
- **Rate / history POSTs** are acknowledged locally (`{"ok":true}`); taste
  events do not reach the workshop from the shell in v1.
- **Artwork:** 224 of 385 bundled tracks carry their real artwork URLs
  (loaded over the network when online); the rest fall back to the
  player's built-in placeholder art.
- The player's original red BRKNHARTED styling is unchanged inside the
  WebView — retheming the player itself to Quantum Void is a v2 item; the
  shell around it (top bar, home, zones) is fully Quantum Void in v1.
- **Not yet device-tested:** WebView HTML5 audio behavior, intent handoff,
  and offline load are verified by construction + APK inspection only.
  That is what P3/P4 are for.

## Build notes (for the next builder)

- javac needs `-encoding UTF-8` (box default is US-ASCII) and `-cp
  android.jar` (NOT `-bootclasspath`) so lambdas resolve
  `LambdaMetafactory` from the JDK; d8 (`--min-api 24`) desugars.
- apksigner `file:` password source reads sequentially — the .pass file's
  two lines exist for exactly that reason.
