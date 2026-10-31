# WATCH + PULSE — Design Note (2026-10-31, Zane; Brandon's direction)

## What Brandon has (verified 2026-10-31 against Google's own pages)
YouTube Premium Lite, bundled free with his paid Google AI Pro (added at
Google I/O, May 2026; auto-activated, plan-manager only). This bundle is
STRONGER than the old standalone Lite:
- Fewer ads on most videos; **offline downloads: YES; background play:
  YES** — for most videos.
- Carve-outs: ads/downloads/background do NOT apply to music content or
  Shorts; no YouTube Music Premium; no continue-watching / Jump Ahead /
  queuing / HQ audio-video extras.

## The design insight
Lite's only real hole is MUSIC — and music is exactly what Aurum Pulse
is. The two products dovetail:
- **Watch zone** = his YouTube: playlists, subscriptions, history, with
  Lite's ad-light playback, downloads, and background play.
- **Pulse zone** = Aurum: his music player, offline-cached played tracks,
  Audius/SoundCloud catalog — covers the music gap Lite leaves open.
Shell per the 2026-10-27 design: Quantum Void purple zones (Pulse /
Build / Fleet / Forge), gold reserved for Aurum, breathing Pulse
indicator, drawer navigation.

## The one engineering truth that shapes the build
Premium entitlements are honored in full ONLY inside Google's official
YouTube app (that's where downloads + background play live). A WebView
wrapper signed into his account keeps playlists + ad-free web playback,
but the web player has NO downloads and unreliable background play.
Unofficial API clients (NewPipe class) strip Premium entirely — rejected.

## Recommended architecture (v1)
Genesis shell app: Pulse native inside (Aurum assets bundled — offline),
Watch as our designed zone surfacing his playlists in our UI, with
playback handed to the official YouTube app so EVERY Lite benefit he
already pays for survives. Embedded-player variant remains v2 if the
handoff feel disappoints.
**P0 DECIDED (Brandon's tap, 2026-10-31 ~12:32 CDT): Shape A — shell +
official YouTube app handoff.** Embedded player is v2-only if ever.

## Build logistics
No Android toolchain currently on zane-box (verified 2026-10-31). Build
runs on: toolchain reinstall here, or S1/penguin in a heal window.
Queued: GHOST-Q-015. Aurum 2.1 APK already delivered to Brandon's hands
2026-10-31 (smoke test pending) — Pulse's content is proven; this job
builds the combined shell around it.
