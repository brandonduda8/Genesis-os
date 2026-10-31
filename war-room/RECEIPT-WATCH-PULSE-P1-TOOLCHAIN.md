# RECEIPT — GHOST-Q-015 Phase 1: Android Toolchain on zane-box

**Date:** 2026-10-31 (~17:33–17:47 UTC)
**Phase:** P1_toolchain (GHOST-Q-015 Watch+Pulse)
**Verdict: PROVEN** — full manual pipeline (aapt2 → javac → d8 → zipalign → apksigner) produced a signed, verified hello-world APK on this box. No Gradle (daemon cannot run here, per AGENTS.md).

## Toolchain (as left standing)

- **SDK root:** `/home/hatch/android-sdk`
- **cmdline-tools:** 23.0 (build 16111833), at `cmdline-tools/latest` — fresh from `dl.google.com/android/repository/commandlinetools-linux-16111833_latest.zip`, 181,052,239 bytes (byte-exact vs `repository2-1.xml`). Previous 12.0 install backed up to `~/workspace/.android-build/cmdline-tools-12.0-backup`.
- **Components** (`sdkmanager --list_installed`):
  - `build-tools;34.0.0` | 34.0.0
  - `platform-tools` | 37.0.1
  - `platforms;android-34` | rev 3 (`android.jar` present)
- **JDK for builds:** `/home/hatch/jdk/temurin-17` — Temurin 17.0.21+9, fresh tarball from Adoptium (193,594,705 bytes), `java`/`javac` verified.
- Disk: 105 GB free before, ~104 GB after. All scratch under `~/workspace/.android-build/`.

## What was broken, and the repairs

1. **Both pre-existing JDKs were dead.** `~/jdk/jdk-17.0.20.1+1` and `~/jdk/jdk-21.0.12.1+1` fail JVM init with "Failed setting boot class path" — their `lib/modules` (jimage) files were pruned from disk. Not repairable in place; replaced by the fresh Temurin 17 above. **P2 must use `JAVA_HOME=~/jdk/temurin-17`; do not use the two `~/jdk/jdk-*` trees.**
2. **Pre-existing SDK (from the Sept 2026 setup) was partial:** `platforms;android-34` and `platform-tools` were intact, but `build-tools/34.0.0` was missing `aapt2`. Fixed by `sdkmanager --uninstall` + reinstall of `build-tools;34.0.0`; `aapt2` restored (6,076,216 bytes) alongside `apksigner`, `d8`, `zipalign`.
3. **sdkmanager could not fetch manifests — stale egress CA truststore.** First attempts: the new 23.0 sdkmanager shim reported "Failed to connect to remote repository"; the 12.0 sdkmanager reported "IO exception while downloading manifest". Root cause: the egress proxy's MITM CA rotated after `~/workspace/.certs/proxy-truststore.jks` was built (2026-09-24), so Java TLS through the proxy failed while curl (system bundle) worked. Fix applied for these runs: rebuilt a JKS from the *current* `/run/hatch/egress-tls/ca-bundle.pem` (121 certs) at `~/workspace/.android-build/proxy-truststore-fresh.jks` and swapped the `-Djavax.net.ssl.trustStore` path in `SDKMANAGER_OPTS` (helper output otherwise unchanged). Manifest fetch then succeeded immediately.
   - **Follow-up flagged (not done — shared infra, outside this phase's scope):** rebuild the shared `~/workspace/.certs/proxy-truststore.jks` from the live bundle so `java-proxy-opts.sh` consumers work without the swap.

## Proof build (manual pipeline, no Gradle)

Project: `~/workspace/.android-build/proof/` — `AndroidManifest.xml` (package `com.genesis.watchpulse.proof`, versionName `0.1-proof`, minSdk 24 / targetSdk 34) + one `MainActivity`.

Steps, all exit 0: `keytool` fresh debug keystore → `aapt2 link` → `javac` (-source/-target 8, bootclasspath `android.jar`) → `d8` (classes.dex, 1,120 bytes) → zip dex into APK → `zipalign -f -p 4` → `apksigner sign` → `apksigner verify --print-certs`.

- **APK:** `/home/hatch/workspace/.android-build/proof/watchpulse-proof.apk`
- **Size:** 8,619 bytes
- **SHA-256:** `365a15e70394b0959997131452e09edcc707ab73b9fc04c5bd906162a4638170`
- **Contents:** `AndroidManifest.xml`, `resources.arsc`, `classes.dex`

**apksigner verify --print-certs (verbatim):**

```
Signer #1 certificate DN: CN=Android Debug, O=Genesis, C=US
Signer #1 certificate SHA-256 digest: f5fabfdcf0270d778e7455975bfc5bc4f42ddcee5b146832014a227bed184d7b
Signer #1 certificate SHA-1 digest: 393aeeea6399749d70dd4ec9e8871c798f19493f
Signer #1 certificate MD5 digest: 8d88968e406bf50ffcd156fbbcf78e40
```

(Verify exited 0, no warnings. Full output preserved at `~/workspace/.android-build/proof/apksigner-verify.txt`.)

## Phase gate

- P0_shape: DECIDED — Shape A (shell + official-app handoff), Brandon tap 2026-10-31.
- P1_toolchain: **PROVEN** by this receipt. zane-box is now a working Android build node; P2 (build v1) is unblocked and needs no heal-window host.
