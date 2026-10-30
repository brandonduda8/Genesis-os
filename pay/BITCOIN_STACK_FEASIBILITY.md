# Bitcoin stack: build / no-build spec (STAGED, nothing installed)

WO-CLAUDE-VAULT-001 mission 3. Prepared 2026-10-30. **Nothing in this document has been installed, configured or run on any host.** Every step on S1 or in an app needs Brandon's named tap.

## Recommendation

| Piece | Verdict | Why |
|---|---|---|
| Watch-only treasury view (Sparrow or BlueWallet) of a wallet Brandon controls | **BUILD first** (Brandon's devices, his tap) | No server, no install on S1, no funds at risk in the viewer. It answers "what do I hold" without exposing keys. |
| BTCPay Server on S1, loopback only | **NO-BUILD now; revisit** | It is a *receiving* processor. Bound to loopback, no outside payer can reach its checkout. Its value starts only when Genesis has customers paying in BTC and a reviewed way to expose checkout. It costs ~50 GB disk plus a full-chain download, and its setup changes the host. |
| Cash App BTC buy + withdrawal to Brandon's own wallet | **Brandon's choice, his hands** | Genesis only documents the path below. It never initiates it (C8). |

## 1. BTCPay Server on S1

Source: the official `btcpayserver/btcpayserver-docker` docs at commit `7670c2f3cea3f1ad98983eaa93f82589d729b6b1`. docs.btcpayserver.org was not reachable from the build sandbox, so the same docs were read from the repo's `docs/` folder. File hashes are in `pay/sources/btcpay/SOURCES.sha256`.

**What it deploys** (README): BTCPay Server, PostgreSQL, NBXplorer, Bitcoin Core, Nginx with automatic HTTPS, and "Tor hidden services and selected Tor connectivity". Lightning is optional (`BTCPAYGEN_LIGHTNING`, default `none`).

**Resources** (`docs/specs.md`):
- Starting point for a small Bitcoin-only deployment: 4 GB RAM, 2 virtual cores, 50 GB usable SSD as a bare minimum.
- Bandwidth must be "enough for the initial full-chain download". Pruning limits what is *kept*, not what is downloaded.
- Storage formula: `root SSD = 10 GB + 15 GB Bitcoin chainstate`, plus the pruning target for blocks. `opt-save-storage-xs` keeps about 25 GB of blocks, so about 50 GB in total before images, database growth and logs. `opt-save-storage-xxs` keeps about 5 GB, but the docs say to avoid it for Lightning.
- Pruning is incompatible with `opt-txindex`, ElectrumX and the bundled Mempool service.

**Fit on S1:** S1's last beacon (genesis-openclaw-mailbox `vantage/genesis-s1.json`, ts 2026-10-24T22:15Z, now about 5 days stale) reported 91.9 GB free disk and 15,140 MB RAM available. That would fit the `-xs` profile with headroom. It is **NOT VERIFIED** today: the beacon is stale, and this session has no access to S1. "Docker 29.9.2 live on S1" is also unverified from here.

**Bind law (loopback only): needs a reviewed custom fragment.**
- The documented host-port variables (`docs/configuration.md`) are port numbers only: `REVERSEPROXY_HTTP_PORT` (default 80), `REVERSEPROXY_HTTPS_PORT` (443), and `NOREVERSEPROXY_HTTP_PORT` (80, used with `BTCPAYGEN_REVERSEPROXY=none`).
- No documented variable takes a bind address. Docker publishes a bare port on all interfaces, so the stock settings would violate the bind law.
- The documented mechanism for changes is a custom fragment (`docs/customization.md`, files ending `.custom.yml`, added with `btcpay-fragments add`).
- A loopback build therefore requires writing that fragment, then checking the *generated* compose (`btcpay-fragments show` and the generated file) before first start. I have not written or tested it, so it is a design, not a verified config.

**What setup changes on the host** (`docs/installation.md`). This is why it needs a tap:
1. Installs Docker if absent, plus the repo's pinned Docker Compose.
2. Writes `$BTCPAY_BASE_DIRECTORY/.env` and `/etc/profile.d/btcpay-env.sh`, symlinks utilities into `/usr/local/bin`, and registers `/etc/systemd/system/btcpayserver.service`.
3. Creates `/etc/docker/daemon.json` if missing. It does not replace an existing one.
4. The recommended `btcpay-host` fragment "changes host SSH configuration". **Exclude it on S1.** Even excluded, setup "still prepares the host key and authorized-key entry".
5. The bundled HTTPS path requires a public domain and inbound ports 80/443. The docs say a domain is not required for local or manually proxied deployments.

**Staged install outline (do not run without the tap):**
1. Confirm current S1 disk, RAM and Docker version.
2. Decide on Tor and the `btcpay-host` exclusion.
3. Write the loopback custom fragment and review the generated compose for any `0.0.0.0` or host-port publication.
4. Source `btcpay-setup.sh -i` with `BTCPAYGEN_REVERSEPROXY=none`, `BTCPAYGEN_LIGHTNING=none` and `opt-save-storage-xs`.
5. Verify with `ss -ltn` that only 127.0.0.1 listens.
6. Wait for initial sync.

Rollback is documented in `docs/backup-restore.md`; the uninstall steps have not been reviewed here.

**Honest limits:**
- BTCPay receives payments. It does not earn yield, convert to dollars, or hold funds for anyone.
- Payments go to a wallet whose keys Brandon controls. The xpub is given to the store; the seed never is.
- On loopback, only someone on S1 can open an invoice page.

## 2. Watch-only treasury view

- **Sparrow** (desktop). The official quick start (sparrowwallet.com/docs/quick-start.html) lists an "xPub / Watch Only Wallet" keystore, and notes ypub/zpub are aliases that identify script type. Import the account's output descriptor or zpub from the wallet Brandon controls; the seed is never entered.
- **BlueWallet** (phone). Official pages (bluewallet.io/watch-only/, bluewallet.io/how-to-set-up-a-watch-only-wallet-in-bluewallet/) say it imports a public address or an extended public key (xpub/ypub/zpub) without moving anything. If the import screen asks for a seed, the wrong QR code was scanned.
- **Privacy, NOT VERIFIED here** (vendor pages blocked from the sandbox): both apps look addresses up through a server. Using a default public server reveals the wallet's addresses to that server operator. Pointing Sparrow at Brandon's own node would avoid that, but needs a node, which is the same cost as item 1.
- **Pitfall** (forum report, not vendor docs): importing Sparrow's default xpub into BlueWallet picked the wrong derivation path; the zpub or descriptor fixed it.

## 3. Cash App: buy BTC, then withdraw to Brandon's own wallet (his hands)

The official help article "Bitcoin Withdrawals" (cash.app/help/3106-bitcoin-withdrawals) was readable only as a search excerpt; cash.app was blocked from the sandbox. What it states:
1. On the home screen, switch from USD to BTC and select Bitcoin.
2. Choose withdraw, then scan the destination wallet's QR code or enter the address manually.

Not stated in anything official I could read: limits, network or Cash App fees, speed options, minimums, or exact verification steps. **Read them in the app before sending.** On-chain sends are irreversible, so check the address on the receiving wallet's own screen first. Never use a "support" phone number from a search result.

## Self-custody is physical

Whoever holds the seed phrase holds the bitcoin. Securing it is Brandon's job alone: offline, never photographed, never typed into Genesis or any chat. Genesis stores xpubs and descriptors at most; it never stores a seed or a private key.
