# Watch+Pulse — source tree (pushed 2026-10-31 to unblock the PAE)

Canonical app sources for `com.genesis.watchpulse`, copied from the
build tree at `~/workspace/.android-build/watchpulse/` on zane-box
(the genesis-os checkout previously held only `builds/`).

Build = the manual pipeline documented in
`war-room/RECEIPT-WATCH-PULSE-P1-TOOLCHAIN.md` and
`war-room/RECEIPT-WATCH-PULSE-P2-BUILD.md` (aapt2 -> javac -> d8 ->
zipalign -> apksigner; Gradle daemon cannot run on zane-box).

Intentionally NOT in git: `builds/watch-pulse-v1.apk` (70,834 B,
sha256 c82cdb09..., delivered to Brandon 2026-10-31), the intermediate
APKs/dex/obj/gen output of the build tree, and the release keystore
(never leaves zane-box).
