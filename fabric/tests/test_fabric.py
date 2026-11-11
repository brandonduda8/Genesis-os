"""Fabric battery: the three acceptance proofs (dark-GitHub, PIN fail-closed, ratchet non-decryption) and the laws."""
import copy
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from genesis_fabric import crypto as C  # noqa: E402
from genesis_fabric.crypto import Chain, FabricError, Keys  # noqa: E402
from genesis_fabric.identity import Registry, issue, new_doc, revoke  # noqa: E402
from genesis_fabric.phone import HttpTransport, LocalTransport, Phone  # noqa: E402
from genesis_fabric.relay import TTL_S, Relay, serve  # noqa: E402

NOW = 1_793_000_000.0


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


def world(names=("zane", "drain", "astra"), relays=1):
    clock, founder = Clock(), Keys.generate()
    keys = {n: Keys.generate() for n in names}
    doc = new_doc(founder, *[issue(founder, name=n, klass="minion" if n == "drain" else "operator", keys=keys[n],
                                   charter_id=f"CH-{n}", now=NOW) for n in names])
    reg = Registry(doc)
    tmp = tempfile.mkdtemp()
    rs = [Relay(os.path.join(tmp, f"r{i}.db"), reg, clock) for i in range(relays)]
    for i, r in enumerate(rs):
        r.label = f"relay{i}"
    phones = {n: Phone(n, keys[n], reg, [LocalTransport(r) for r in rs], clock,
                       state_path=os.path.join(tmp, f"{n}.state")) for n in names}
    return {"clock": clock, "founder": founder, "keys": keys, "doc": doc, "reg": reg, "relays": rs, "phones": phones,
            "tmp": tmp}


def pair(w, a, b):
    pa, pb = w["phones"][a].pair_begin(b), w["phones"][b].pair_begin(a)
    assert pa == pb  # the same root on both sides: the two operators see the same PIN
    w["phones"][a].pair_confirm(b, pb)
    w["phones"][b].pair_confirm(a, pa)
    w["phones"][a].poll()
    w["phones"][b].poll()


class Primitives(unittest.TestCase):
    def test_hkdf_rfc5869_case1(self):
        okm = C.hkdf(bytes.fromhex("0b" * 22), salt=bytes.fromhex("000102030405060708090a0b0c"),
                     info=bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), length=42)
        self.assertEqual(okm.hex(), "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")

    def test_unsigned_or_forged_identities_do_not_exist(self):
        w = world()
        doc = copy.deepcopy(w["doc"])
        doc["identities"][0]["record"]["class"] = "founder"  # forged edit
        mallory = Keys.generate()
        doc["identities"].append(issue(mallory, name="mallory", klass="operator", keys=mallory, charter_id="x", now=NOW))
        reg = Registry(doc)
        with self.assertRaises(FabricError):
            reg.get("zane")
        with self.assertRaises(FabricError):
            reg.get("mallory")
        with self.assertRaises(FabricError):
            issue(w["founder"], name="x", klass="m", keys=mallory, charter_id="", now=NOW)


class PinCeremony(unittest.TestCase):
    """Acceptance proof 2: the PIN ceremony fails closed."""

    def test_happy_path_activates_both_sides(self):
        w = world()
        pair(w, "zane", "drain")
        self.assertEqual(w["phones"]["zane"].sessions["drain"]["state"], "ACTIVE")
        self.assertEqual(w["phones"]["drain"].sessions["zane"]["state"], "ACTIVE")

    def test_wrong_pin_destroys_the_pairing_and_nothing_can_be_sent(self):
        w = world()
        z = w["phones"]["zane"]
        pin = z.pair_begin("drain")
        wrong = "%06d" % ((int(pin) + 1) % 1_000_000)
        with self.assertRaises(FabricError) as cm:
            z.pair_confirm("drain", wrong)
        self.assertIn("destroyed", str(cm.exception))
        self.assertNotIn("drain", z.sessions)
        with self.assertRaises(FabricError):
            z.send("drain", {"x": 1})

    def test_one_sided_confirm_is_not_active(self):
        w = world()
        z, d = w["phones"]["zane"], w["phones"]["drain"]
        pin = z.pair_begin("drain")
        d.pair_begin("zane")
        z.pair_confirm("drain", pin)  # drain's operator never confirms
        z.poll()
        with self.assertRaises(FabricError):
            z.send("drain", {"x": 1})
        d.poll()  # drain gets zane's ack but has not confirmed itself
        with self.assertRaises(FabricError):
            d.send("zane", {"x": 1})

    def test_timeout_destroys(self):
        w = world()
        z = w["phones"]["zane"]
        pin = z.pair_begin("drain")
        w["clock"].t += 601
        with self.assertRaises(FabricError):
            z.pair_confirm("drain", pin)
        self.assertNotIn("drain", z.sessions)

    def test_substituted_key_shows_a_different_pin(self):
        """If someone swaps drain's registry key, zane's operator sees a PIN that drain's operator does not."""
        w = world()
        evil = Keys.generate()
        doc = copy.deepcopy(w["doc"])
        doc["identities"] = [e for e in doc["identities"] if e["record"]["name"] != "drain"]
        doc["identities"].append(issue(w["founder"], name="drain", klass="minion", keys=evil, charter_id="CH-drain",
                                       now=NOW))
        z_view = Phone("zane", w["keys"]["zane"], Registry(doc), [], w["clock"])
        self.assertNotEqual(z_view.pair_begin("drain"), w["phones"]["drain"].pair_begin("zane"))


class Messaging(unittest.TestCase):
    def test_send_poll_decrypt_ack_and_relay_never_sees_plaintext(self):
        w = world()
        pair(w, "zane", "drain")
        w["phones"]["drain"].send("zane", {"report": "Q-002 drained", "secret": "s3cr3t-marker"})
        raw = w["relays"][0].db.execute("SELECT env FROM queue").fetchall()
        self.assertNotIn("s3cr3t-marker", json.dumps(raw))
        got = w["phones"]["zane"].poll()
        self.assertEqual(got[0]["body"]["report"], "Q-002 drained")
        self.assertEqual(w["relays"][0].depth(), 0)  # acked = deleted

    def test_replay_and_tamper_and_misroute_refused(self):
        w = world()
        pair(w, "zane", "drain")
        r = w["relays"][0]
        w["phones"]["drain"].send("zane", {"n": 1})
        env = json.loads(r.db.execute("SELECT env FROM queue").fetchone()[0])
        with self.assertRaises(FabricError):
            r.accept(env)  # replay
        bad = dict(env, id="other", ts=env["ts"])
        with self.assertRaises(FabricError):
            r.accept(bad)  # id is signed: changing it breaks the signature
        t = dict(env)
        ct = bytearray(C.unb64(t["ct"]))
        ct[0] ^= 1
        t["ct"] = C.b64(bytes(ct))
        with self.assertRaises(FabricError):
            r.accept(t)

    def test_revoked_identity_refused_everywhere(self):
        w = world()
        pair(w, "zane", "drain")
        doc = dict(w["doc"], revoked=[revoke(w["founder"], "drain", NOW)])
        reg = Registry(doc)
        r = Relay(os.path.join(w["tmp"], "rv.db"), reg, w["clock"])
        p = Phone("drain", w["keys"]["drain"], reg, [LocalTransport(r)], w["clock"])
        p.sessions = w["phones"]["drain"].sessions
        with self.assertRaises(FabricError):
            p.send("zane", {"x": 1})

    def test_out_of_order_delivery(self):
        a, b = Chain(b"k" * 32), Chain(b"k" * 32)
        keys = [a.next_send() for _ in range(4)]
        for n, mk in (keys[2], keys[0], keys[3], keys[1]):
            self.assertEqual(b.key_for(n), mk)
        with self.assertRaises(FabricError):
            b.key_for(1)  # each key once


class Ratchet(unittest.TestCase):
    """Acceptance proof 3: a later stolen state cannot decrypt captured earlier ciphertext."""

    def test_captured_ciphertext_cannot_be_decrypted_from_later_state(self):
        w = world()
        pair(w, "zane", "drain")
        d, z, r = w["phones"]["drain"], w["phones"]["zane"], w["relays"][0]
        d.send("zane", {"msg": "first"})
        captured = json.loads(r.db.execute("SELECT env FROM queue").fetchone()[0])  # the attacker records it
        for i in range(4):
            d.send("zane", {"msg": i})
        z.poll()
        stolen = Chain.from_state(json.loads(json.dumps(z.sessions["drain"]["recv"].state())))  # state at n=5
        self.assertEqual(stolen.n, 5)
        with self.assertRaises(FabricError):
            stolen.key_for(captured["hdr"]["n"])  # key 0 was erased
        # and no forward walk from the stolen chain key ever reproduces message key 0
        probe = Chain.from_state(json.loads(json.dumps(z.sessions["drain"]["recv"].state())))
        tried = [probe.key_for(probe.n + i) for i in range(10)]
        from genesis_fabric.envelope import header
        for k in tried:
            with self.assertRaises(FabricError):
                C.open_(k, 0, captured["ct"], C.canon(header(captured)))


class Rooms(unittest.TestCase):
    def test_room_messages_and_removed_member_locked_out(self):
        w = world()
        pair(w, "zane", "drain")
        pair(w, "zane", "astra")
        z, d, a = (w["phones"][n] for n in ("zane", "drain", "astra"))
        z.room_create("ops", ["drain", "astra"])
        d.poll()
        a.poll()
        z.room_send("ops", {"hello": "room"})
        self.assertEqual(d.poll()[0]["body"], {"hello": "room"})
        a.poll()
        z.room_remove("ops", "drain")
        d.poll()  # drain receives nothing for the new epoch (it is not sent the key)
        a.poll()
        z.room_send("ops", {"after": "removal"})
        self.assertEqual(a.poll()[0]["body"], {"after": "removal"})
        self.assertEqual(d.rooms["ops"]["epoch"], 1)  # stuck on the old epoch
        self.assertEqual(w["relays"][0].depth("drain"), 0)  # nothing new was even addressed to drain


class Durability(unittest.TestCase):
    def test_relay_survives_recycle_mid_flow(self):
        w = world()
        pair(w, "zane", "drain")
        w["phones"]["drain"].send("zane", {"before": "recycle"})
        path = os.path.join(w["tmp"], "r0.db")
        w["relays"][0].close()  # the node recycles
        r2 = Relay(path, w["reg"], w["clock"])
        w["phones"]["zane"].transports = [LocalTransport(r2)]
        self.assertEqual(w["phones"]["zane"].poll()[0]["body"], {"before": "recycle"})

    def test_phone_state_survives_restart(self):
        w = world()
        pair(w, "zane", "drain")
        d = w["phones"]["drain"]
        d.send("zane", {"a": 1})
        d2 = Phone("drain", w["keys"]["drain"], w["reg"], d.transports, w["clock"], state_path=d.state_path)
        d2.send("zane", {"a": 2})
        self.assertEqual([m["body"]["a"] for m in w["phones"]["zane"].poll()], [1, 2])

    def test_expiry_writes_receipts(self):
        w = world()
        pair(w, "zane", "drain")
        w["phones"]["drain"].send("zane", {"x": 1})
        w["clock"].t += TTL_S + 1
        self.assertEqual(w["relays"][0].expire(), 1)
        self.assertEqual(w["relays"][0].db.execute("SELECT event FROM receipts WHERE event='expired'").fetchone()[0],
                         "expired")

    def test_failover_to_replica_and_dedupe(self):
        w = world(relays=2)
        pair(w, "zane", "drain")
        w["phones"]["drain"].send("zane", {"x": "both"})
        self.assertEqual(len(w["phones"]["zane"].poll()), 1)  # delivered by both relays, seen once

        class Dark:
            name = "dark"

            def send(self, *a):
                raise OSError("S1 unreachable")
            fetch = ack = send
        w["phones"]["drain"].transports[0] = Dark()
        w["phones"]["zane"].transports[0] = Dark()
        w["phones"]["drain"].send("zane", {"x": "replica only"})
        self.assertEqual(w["phones"]["zane"].poll()[0]["body"], {"x": "replica only"})


class DarkGitHub(unittest.TestCase):
    """Acceptance proof 1: with every outbound host blocked except the relay, the fabric works end to end."""

    def test_full_cycle_over_http_with_only_the_relay_reachable(self):
        w = world()
        srv = serve(w["relays"][0], "127.0.0.1", 0)
        port = srv.server_address[1]
        real_connect = socket.socket.connect

        def guarded(sock, addr):
            if isinstance(addr, tuple) and addr[0] == "127.0.0.1" and addr[1] == port:
                return real_connect(sock, addr)
            raise ConnectionRefusedError(f"DARK: {addr} blocked (github and everything else)")
        socket.socket.connect = guarded
        old_proxy = {k: os.environ.pop(k) for k in list(os.environ) if k.lower() in ("https_proxy", "http_proxy",
                                                                                      "all_proxy", "no_proxy")}
        try:
            with self.assertRaises(Exception):
                urllib.request.urlopen("https://api.github.com", timeout=2)
            for p in w["phones"].values():
                p.transports = [HttpTransport(f"http://127.0.0.1:{port}")]
            pair(w, "zane", "drain")
            w["phones"]["drain"].send("zane", {"status": "github is dark; fabric is not"})
            got = w["phones"]["zane"].poll()
            self.assertEqual(got[0]["body"]["status"], "github is dark; fabric is not")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/presence") as r:
                pres = json.loads(r.read())["presence_age_s"]
            self.assertEqual(pres["zane"], 0)
            self.assertIsNone(pres["astra"])  # never fetched: presence is observed, not declared
            req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/fetch", data=b"{}", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 403)  # unsigned fetch refused
        finally:
            socket.socket.connect = real_connect
            os.environ.update(old_proxy)
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
