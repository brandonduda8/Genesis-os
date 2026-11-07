// Pulse: SoundCloud through the official widget only (Q-POL-001 ruling A).
// Runs the REAL assets/aurum/index.html + tracks.json in headless Chromium, served exactly as PulseActivity serves
// them (fake origin https://aurum.watchpulse.local). w.soundcloud.com is replaced by a recording stub of the public
// Widget API (SC.Widget: bind/load/play/pause/isPaused/seekTo + Events), so the test proves Pulse's behaviour, not
// SoundCloud's. Real playback on the phone is a separate device check.
//   node watch-pulse/tests/pulse_soundcloud.test.js
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const AURUM = path.join(__dirname, "..", "assets", "aurum");
const HOST = "https://aurum.watchpulse.local";

const STUB = `
window.__sc = { loads: [], calls: [], handlers: {} };
window.SC = { Widget: Object.assign(function (iframe) {
    __sc.loads.push(iframe.src);
    const w = {
      bind(ev, fn) { (__sc.handlers[ev] = __sc.handlers[ev] || []).push(fn); },
      load(url, opts) { __sc.loads.push(url); __sc.calls.push("load"); },
      play() { __sc.calls.push("play"); __sc.paused = false; __sc.fire("play"); },
      pause() { __sc.calls.push("pause"); __sc.paused = true; __sc.fire("pause"); },
      isPaused(cb) { cb(!!__sc.paused); },
      seekTo(ms) { __sc.calls.push("seekTo:" + Math.round(ms)); },
    };
    return w;
  }, { Events: { PLAY: "play", PAUSE: "pause", PLAY_PROGRESS: "playProgress", FINISH: "finish", ERROR: "error" } }) };
__sc.fire = (ev, arg) => (__sc.handlers[ev] || []).forEach(f => f(arg));
`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const external = [], pageErrors = [];
  page.on("pageerror", e => pageErrors.push(e.message));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin === HOST) {
      const map = { "/aurum": "index.html", "/": "index.html", "/api/aurum/tracks": "tracks.json" };
      const f = map[url.pathname];
      if (!f) return route.fulfill({ status: url.pathname.startsWith("/api/") ? 200 : 404, body: "{\"ok\":true}" });
      return route.fulfill({ status: 200, body: fs.readFileSync(path.join(AURUM, f)),
        contentType: f.endsWith(".json") ? "application/json" : "text/html" });
    }
    external.push(url.href);
    if (url.href === "https://w.soundcloud.com/player/api.js")
      return route.fulfill({ status: 200, body: STUB, contentType: "text/javascript" });
    if (url.hostname === "w.soundcloud.com") return route.fulfill({ status: 200, body: "<html></html>", contentType: "text/html" });
    return route.fulfill({ status: 204, body: "" }); // artwork / Audius: not under test
  });
  await page.goto(HOST + "/aurum");
  await page.waitForFunction(() => document.querySelectorAll(".tab").length > 3);

  // 1. Both waiting playlists are back as normal Pulse tabs, with every track.
  const counts = await page.evaluate(() => ({
    aadity: DB.tracks.filter(t => (t.playlists || []).includes("Tha Aadity")).length,
    ghost: DB.tracks.filter(t => (t.playlists || []).includes("Ghostlands")).length,
    tabs: [...document.querySelectorAll(".tab")].map(b => b.textContent) }));
  assert.strictEqual(counts.aadity, 50, "Tha Aadity has all 50 tracks");
  assert.strictEqual(counts.ghost, 11, "Ghostlands has all 11 tracks");
  assert.ok(counts.tabs.includes("Tha Aadity") && counts.tabs.includes("Ghostlands"), "tabs exist");

  // 2. Tapping a SoundCloud track plays it through the official widget, visibly, not through <audio>.
  await page.click('.tab[data-k="pl:Tha Aadity"]');
  await page.click("#list .row >> nth=0");
  await page.waitForFunction(() => window.__sc && __sc.loads.length > 0);
  const first = await page.evaluate(() => ({ load: __sc.loads[0], shown: getComputedStyle($("scwrap")).display,
    audioSrc: $("audio").getAttribute("src"), title: $("ntitle").textContent, cur: queue[qi] }));
  assert.ok(first.load.startsWith("https://w.soundcloud.com/player/?url=https%3A%2F%2Fsoundcloud.com%2F"), first.load);
  assert.strictEqual(first.shown, "block", "widget is visible (SoundCloud branding shown)");
  assert.ok(!first.audioSrc, "the <audio> element is not used for SoundCloud");
  assert.strictEqual(first.title, first.cur.title);

  // 3. Progress drives the seek bar; FINISH advances to the next SoundCloud track via widget.load.
  await page.evaluate(() => { __sc.fire("play"); __sc.fire("playProgress", { currentPosition: 30000, relativePosition: 0.25 }); });
  assert.strictEqual(await page.textContent("#cur"), "0:30");
  assert.strictEqual(await page.textContent("#dur"), "2:00");
  const before = await page.evaluate(() => qi);
  await page.evaluate(() => __sc.fire("finish"));
  const after = await page.evaluate(() => ({ qi, loads: __sc.loads.length, url: __sc.loads[__sc.loads.length - 1],
    want: queue[qi].soundcloud_url }));
  assert.strictEqual(after.qi, before + 1, "FINISH advances the queue");
  assert.strictEqual(after.url, after.want, "next track loaded into the same widget");

  // 4. Play/pause and seek control the widget, not <audio>.
  await page.evaluate(() => { __sc.paused = false; });
  await page.click("#play");
  await page.evaluate(() => __sc.fire("playProgress", { currentPosition: 10000, relativePosition: 0.1 }));
  await page.evaluate(() => { const s = $("seek"); s.value = 500; s.dispatchEvent(new Event("input")); });
  const calls = await page.evaluate(() => __sc.calls);
  assert.ok(calls.includes("pause"), "toggle pauses the widget");
  assert.ok(calls.includes("seekTo:50000"), "seek goes to the widget: " + calls.join(","));

  // 5. Switching to a normal Audius track hides and pauses the widget and uses <audio> again.
  await page.click('.tab[data-k="all"]');
  await page.evaluate(() => { const i = DB.tracks.findIndex(t => t.stream_url); playFrom(DB.tracks, i); });
  const back = await page.evaluate(() => ({ shown: getComputedStyle($("scwrap")).display,
    src: $("audio").getAttribute("src") || "" }));
  assert.strictEqual(back.shown, "none");
  assert.ok(back.src.includes("audius"), "Audius plays through <audio>");

  // 6. Offline: a SoundCloud track says so honestly and is skipped; nothing pretends to be cached.
  await page.context().setOffline(true);
  await page.evaluate(() => { const l = DB.tracks.filter(t => t.soundcloud_url); playFrom(l, 0); });
  await page.waitForFunction(() => /SoundCloud needs a connection/.test($("status").textContent), null, { timeout: 3000 });
  await page.context().setOffline(false);

  // 7. Only the official widget host is ever contacted for SoundCloud: no api-v2, no client_id, no media CDN.
  const sc = external.filter(u => /soundcloud|sndcdn/.test(u) && !u.startsWith("https://i1.sndcdn.com/"));
  assert.ok(sc.length > 0 && sc.every(u => u.startsWith("https://w.soundcloud.com/")), sc.join("\n"));
  assert.ok(!external.some(u => /api-v2\.soundcloud|client_id=/.test(u)));

  assert.deepStrictEqual(pageErrors, [], "no uncaught JS errors in Pulse");
  await browser.close();
  console.log("pulse_soundcloud: 8 checks OK (" + sc.length + " SoundCloud requests, all to w.soundcloud.com)");
})().catch(e => { console.error("FAIL:", e.message); process.exit(1); });
