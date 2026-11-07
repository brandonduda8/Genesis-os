# RECEIPT — Watch+Pulse: SoundCloud playlists back in Pulse through the official widget

**Queue:** GHOST-Q-015 (Watch+Pulse) · **Policy:** Q-POL-001 ruling **A** (Brandon, 2026-10-31) · **Builder:** Claude
(Power Autonomous Engineer, GHOST-Q-018) · **Verifier:** Zane · **Certifier:** Brandon

**Grade: BUILT.** Browser-tested against the real Pulse assets. It is **not yet in a new APK and not yet on Brandon's
phone.**

## What changed

**`watch-pulse/assets/aurum/tracks.json`** (additions only, 799 lines)
- The **Tha Aadity** playlist (50 tracks) and the **Ghostlands** playlist (11 tracks) are back. Tha Aadity is first
  in the playlist order, as it is in Aurum.
- They come from Aurum's catalog, genesis-player@`41d1469`. Each track carries only its public `soundcloud.com/…`
  page link plus title, artist and artwork. There are no stream URLs and no keys.

**`watch-pulse/assets/aurum/index.html`** (+72/−3)
- A SoundCloud track plays in **SoundCloud's own widget** (`w.soundcloud.com`). The widget stays visible with
  SoundCloud's branding, above the player bar.
- It joins the normal queue: next/previous, play/pause and seek all control the widget; FINISH moves to the next
  track; an error or stall skips, the same as Audius.
- When an Audius track plays, the widget pauses and hides.
- Offline, a SoundCloud track says "needs a connection" and is skipped. It is never cached.
- **Aurum's scraped-key resolver is not used or copied**, per ruling A.

No Java change was needed: `PulseActivity` already passes real-network hosts through, and it already sets
`setMediaPlaybackRequiresUserGesture(false)`.

## Evidence

**`node watch-pulse/tests/pulse_soundcloud.test.js` → `8 checks OK`.** It runs headless Chromium (Playwright) on the
**real** `index.html` and `tracks.json`, served under the app's own origin, `https://aurum.watchpulse.local`. The
eight checks:

1. The tabs exist, with exactly 50 and 11 tracks.
2. A tap loads `https://w.soundcloud.com/player/?url=https%3A%2F%2Fsoundcloud.com%2F…`. The widget is visible, and
   `<audio>` is unused.
3. Progress drives the seek bar (0:30 / 2:00), and FINISH advances to the next track in the same widget.
4. Play/pause and seek go to the widget (`seekTo:50000`).
5. Switching to Audius hides the widget and plays through `<audio>`.
6. Offline gives an honest "needs a connection".
7. Every SoundCloud request goes to `w.soundcloud.com` (the artwork CDN aside). There are no `api-v2` or `client_id`
   requests.
8. No uncaught JavaScript errors.

**Fail-before:** the same test against main's `index.html` times out, because main's player can't play these tracks.

**Limits:** `w.soundcloud.com` is unreachable from the build container. The test therefore uses a recording stub of
SoundCloud's public Widget API (`SC.Widget`: bind, load, play, pause, isPaused, seekTo, Events). It proves Pulse's
behaviour, not SoundCloud's. Real audio needs the device check below.

## Owed (Zane, then Brandon)

1. **Rebuild the APK** with the manual pipeline (`RECEIPT-WATCH-PULSE-P1-TOOLCHAIN.md`): aapt2, javac, d8, zipalign,
   apksigner. Only the assets changed.
2. **On the phone:** open Pulse → **Tha Aadity** → tap a track. It should play audibly, the widget should show
   SoundCloud branding, and it should auto-advance at the end. Repeat once for **Ghostlands**.
3. If the widget won't autoplay in the WebView on his Android version, report it. The fix is a one-tap "play" inside
   the widget, still within ruling A.
