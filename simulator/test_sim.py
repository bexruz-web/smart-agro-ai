"""Smart Agro AI simulyatori uchun testlar.

Ishga tushirish (ikkalasi ham ishlaydi):
    python3 -m pytest simulator/test_sim.py -q
    python3 -m unittest discover -s simulator -p "test_*.py" -v
"""
from __future__ import annotations

import io
import json
import math
import re
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sim  # noqa: E402

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ALLOWED_READING_KEYS = set(sim.READING_KEYS)
TOP_KEYS = {"device_id", "fw", "seq", "rssi", "battery_v", "readings"}
LAT, LON = 40.12, 67.84
T0 = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)
SUMMER_T0 = datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc)


def series(scenario: str, hours: float = 24, step_min: float = 15, start: datetime = T0,
           seed: int = 42) -> list[dict]:
    m = sim.FieldModel(scenario=scenario, seed=seed, lat=LAT, lon=LON)
    n = int(hours * 60 / step_min)
    return [m.next_reading(start + timedelta(minutes=step_min * i)) for i in range(n)]


def live_series(scenario: str, n: int = 20, seed: int = 7) -> list[dict]:
    """Jonli demo: real vaqt, 15 s oraliq."""
    m = sim.FieldModel(scenario=scenario, seed=seed, lat=LAT, lon=LON)
    t = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)   # Toshkent ~13:00
    return [m.next_reading(t + timedelta(seconds=15 * i)) for i in range(n)]


def local_hour(ts: str) -> float:
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return sim.solar_hour(t, LON)


def check_payload_schema(tc: unittest.TestCase, p: dict) -> None:
    tc.assertTrue(set(p) <= TOP_KEYS, set(p) - TOP_KEYS)
    for k in ("device_id", "fw", "seq", "rssi", "readings"):
        tc.assertIn(k, p)
    tc.assertIsInstance(p["device_id"], str)
    tc.assertIsInstance(p["fw"], str)
    tc.assertIsInstance(p["seq"], int)
    tc.assertIsInstance(p["rssi"], int)
    if "battery_v" in p:
        tc.assertIsInstance(p["battery_v"], float)
    tc.assertIsInstance(p["readings"], list)
    tc.assertTrue(1 <= len(p["readings"]) <= sim.MAX_READINGS_PER_POST)
    for r in p["readings"]:
        tc.assertTrue(set(r) <= ALLOWED_READING_KEYS, set(r) - ALLOWED_READING_KEYS)
        tc.assertRegex(r["ts"], TS_RE)
        tc.assertIsInstance(r["soil_moisture_raw"], int)
        tc.assertIsInstance(r["rain"], bool)
        tc.assertIsInstance(r["light_lux"], int)
        for k in ("soil_moisture_vwc", "soil_temp_c", "air_temp_c", "air_rh"):
            tc.assertIsInstance(r[k], (int, float))
            tc.assertFalse(isinstance(r[k], bool))
            tc.assertTrue(math.isfinite(r[k]))
    json.dumps(p, allow_nan=False)   # NaN/Infinity bo'lmasligi kerak


class ModelRangesTest(unittest.TestCase):
    def test_normal_value_ranges(self):
        for start in (T0, SUMMER_T0):
            for r in series("normal", hours=48, start=start):
                self.assertTrue(0 <= r["soil_moisture_vwc"] <= 60)
                self.assertTrue(0 <= r["soil_moisture_raw"] <= 4095)
                self.assertTrue(-30 <= r["air_temp_c"] <= 50, r)
                self.assertTrue(0 <= r["air_rh"] <= 100)
                self.assertTrue(-10 <= r["soil_temp_c"] <= 45)
                self.assertGreaterEqual(r["light_lux"], 0)
                self.assertLessEqual(r["light_lux"], 130000)
                self.assertFalse(r["rain"])

    def test_light_follows_sun(self):
        rs = series("normal", hours=24)
        night = [r["light_lux"] for r in rs if local_hour(r["ts"]) < 5 or local_hour(r["ts"]) > 19.5]
        noon = [r["light_lux"] for r in rs if 11.5 <= local_hour(r["ts"]) <= 12.5]
        self.assertTrue(night and all(v == 0 for v in night))
        self.assertTrue(noon and min(noon) > 15000)

    def test_diurnal_air_temperature(self):
        rs = series("normal", hours=24)
        afternoon = [r["air_temp_c"] for r in rs if 14 <= local_hour(r["ts"]) <= 16]
        dawn = [r["air_temp_c"] for r in rs if 5 <= local_hour(r["ts"]) <= 7]
        self.assertGreater(min(afternoon) - max(dawn), 6.0)
        # namlik haroratga teskari
        rh_aft = sum(r["air_rh"] for r in rs if 14 <= local_hour(r["ts"]) <= 16)
        rh_dawn = sum(r["air_rh"] for r in rs if 5 <= local_hour(r["ts"]) <= 7)
        self.assertLess(rh_aft, rh_dawn)

    def test_soil_temperature_lags_and_damps(self):
        rs = series("normal", hours=72, start=SUMMER_T0)[-96:]   # oxirgi sutka
        air = [r["air_temp_c"] for r in rs]
        soil = [r["soil_temp_c"] for r in rs]
        self.assertLess(max(soil) - min(soil), max(air) - min(air))   # amplituda kichik
        i_air, i_soil = air.index(max(air)), soil.index(max(soil))
        self.assertGreater(i_soil, i_air)                              # maksimum kechikadi

    def test_normal_soil_slowly_dries(self):
        rs = series("normal", hours=72, start=SUMMER_T0)
        first, last = rs[0]["soil_moisture_vwc"], rs[-1]["soil_moisture_vwc"]
        self.assertLess(last, first)
        self.assertGreater(last, first - 12)   # sekin, keskin emas

    def test_raw_is_inverse_of_vwc(self):
        rs = series("normal", hours=6)
        for r in rs:
            expected = sim.vwc_to_raw(r["soil_moisture_vwc"])
            self.assertLess(abs(r["soil_moisture_raw"] - expected), 40)


class ScenarioTest(unittest.TestCase):
    def test_drought_decreasing_and_hot(self):
        rs = live_series("drought", n=20)
        vwc = [r["soil_moisture_vwc"] for r in rs]
        self.assertLess(vwc[-1], 15.0)
        self.assertLess(vwc[-1], vwc[0] - 6)
        rises = [b - a for a, b in zip(vwc, vwc[1:]) if b - a > 0.6]
        self.assertEqual(rises, [], "qurg'oqchilikda namlik sezilarli oshmasligi kerak")
        first_below = next(i for i, v in enumerate(vwc) if v < 15)
        self.assertLessEqual(first_below, 12, "15% dan pastga tez tushishi kerak")
        normal = live_series("normal", n=20)
        self.assertGreater(rs[-1]["air_temp_c"], normal[-1]["air_temp_c"] + 6)
        self.assertLess(rs[-1]["air_rh"], normal[-1]["air_rh"])
        self.assertFalse(any(r["rain"] for r in rs))

    def test_drought_backfill_stays_dry(self):
        rs = series("drought", hours=48)
        self.assertLess(max(r["soil_moisture_vwc"] for r in rs[24:]), 15.0)

    def test_heavy_rain(self):
        rs = live_series("heavy_rain", n=20)
        self.assertTrue(all(r["rain"] for r in rs))
        self.assertGreaterEqual(rs[-1]["soil_moisture_vwc"], 40.0)
        self.assertGreater(rs[-1]["soil_moisture_vwc"], rs[0]["soil_moisture_vwc"] + 15)
        self.assertGreater(rs[-1]["air_rh"], 85)

    def test_frost_negative_at_night(self):
        rs = series("frost", hours=36)
        nights = [r for r in rs[RAMP_SKIP:] if local_hour(r["ts"]) < 8 or local_hour(r["ts"]) > 20]
        self.assertTrue(nights)
        self.assertLess(min(r["air_temp_c"] for r in nights), 0.0)
        coldest = min(rs, key=lambda r: r["air_temp_c"])
        h = local_hour(coldest["ts"])
        self.assertTrue(h < 8 or h > 20, f"eng sovuq payt tunda bo'lishi kerak, {h:.1f}")

    def test_sensor_fault_stuck_and_spike(self):
        rs = live_series("sensor_fault", n=20)
        vwc = [r["soil_moisture_vwc"] for r in rs]
        raw = [r["soil_moisture_raw"] for r in rs]
        tail = vwc[sim.FAULT_START_STEP:]
        self.assertEqual(len(set(tail)), 1, "namlik qotib qolishi kerak")
        self.assertEqual(len(set(raw[sim.FAULT_START_STEP:])), 1)
        self.assertGreaterEqual(len(tail), 10)
        spikes = [r["air_temp_c"] for r in rs if r["air_temp_c"] >= 80]
        self.assertGreaterEqual(len(spikes), 2)
        self.assertEqual(rs[sim.FAULT_SPIKE_FIRST]["air_temp_c"], sim.FAULT_SPIKE_VALUE)

    def test_seed_reproducible(self):
        self.assertEqual(series("normal", hours=2, seed=5), series("normal", hours=2, seed=5))
        self.assertNotEqual(series("normal", hours=2, seed=5), series("normal", hours=2, seed=6))

    def test_unknown_scenario(self):
        with self.assertRaises(ValueError):
            sim.FieldModel(scenario="tornado")


RAMP_SKIP = sim.RAMP_STEPS


class FakeServer:
    """Kontrakt bo'yicha javob qaytaradigan soxta sender (seq dedupe bilan)."""

    def __init__(self, token="sa_test", status=200):
        self.token = token
        self.status = status
        self.payloads: list[dict] = []
        self.sent_at: list[datetime] = []
        self.seen: set = set()

    def __call__(self, url, token, payload):
        if token != self.token:
            return 401, {"detail": "Noto'g'ri qurilma tokeni"}
        if self.status != 200:
            return self.status, {"detail": "xato"}
        self.payloads.append(json.loads(json.dumps(payload)))
        self.sent_at.append(sim.utc_now())
        key = (payload["device_id"], payload["seq"])
        dup = key in self.seen
        self.seen.add(key)
        return 200, {"accepted": 0 if dup else len(payload["readings"]),
                     "duplicate_batch": dup, "flagged": 0}


def make_device(tmp: Path, scenario="normal", sender=None, **kw) -> sim.VirtualDevice:
    state = sim.StateStore(tmp / "state.json")
    return sim.VirtualDevice("esp32-test", "sa_test", scenario, "http://x/api/v1", state,
                             sender=sender, seed=3, out=io.StringIO(), **kw)


class DeviceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_payload_schema_matches_contract(self):
        srv = FakeServer()
        dev = make_device(self.tmp, sender=srv)
        for i in range(3):
            t = sim.utc_now() + timedelta(seconds=15 * i)
            dev.run_cycle(dev.make_readings(t, 4, 60))
        self.assertEqual(len(srv.payloads), 3)
        for p in srv.payloads:
            check_payload_schema(self, p)
            self.assertEqual(p["device_id"], "esp32-test")
            self.assertEqual(len(p["readings"]), 4)
            tss = [r["ts"] for r in p["readings"]]
            self.assertEqual(tss, sorted(tss))
        self.assertEqual(set(srv.payloads[0]), TOP_KEYS)

    def test_contract_example_shape(self):
        p = sim.build_payload("esp32-7f3a", 1842, [{
            "ts": "2026-11-14T09:00:00Z", "soil_moisture_raw": 2310, "soil_moisture_vwc": 24.1,
            "soil_temp_c": 19.2, "air_temp_c": 28.0, "air_rh": 41.5, "rain": False,
            "light_lux": 35000}], rssi=-71, battery_v=3.92, fw="0.1.0")
        self.assertEqual(list(p), ["device_id", "fw", "seq", "rssi", "battery_v", "readings"])
        check_payload_schema(self, p)

    def test_seq_monotonic_and_persisted(self):
        path = self.tmp / "state.json"
        s1 = sim.StateStore(path)
        a, b = s1.next_seq("d1"), s1.next_seq("d1")
        self.assertEqual(b, a + 1)
        s2 = sim.StateStore(path)                 # "qayta ishga tushirish"
        c = s2.next_seq("d1")
        self.assertEqual(c, b + 1)
        d2_first = s2.next_seq("d2")               # har qurilmaning o'z hisoblagichi
        self.assertEqual(s2.next_seq("d2"), d2_first + 1)
        self.assertEqual(s2.next_seq("d1"), c + 1)
        c += 1
        self.assertEqual(json.loads(path.read_text())["devices"]["d1"]["seq"], c)

    def test_seq_not_persisted_in_dry_run(self):
        path = self.tmp / "state.json"
        s = sim.StateStore(path, persist=False)
        s.next_seq("d1")
        self.assertFalse(path.exists())

    def test_offline_buffers_then_sends_late_with_original_ts(self):
        srv = FakeServer()
        dev = make_device(self.tmp, scenario="offline", sender=srv, offline_batches=3,
                          online_batches=2)
        base = sim.utc_now() - timedelta(minutes=10)
        generated = []
        for i in range(6):                       # 2 online, 3 offline, 1 flush
            t = base + timedelta(seconds=15 * i)
            rs = dev.make_readings(t, 1, 15)
            generated.extend(rs)
            dev.run_cycle(rs)
            if i < 2:
                self.assertEqual(len(srv.payloads), i + 1)
            elif i < 5:
                self.assertEqual(len(srv.payloads), 2, "offline paytida yuborilmasligi kerak")
        # flush: 3 ta buferlangan + 1 joriy = bitta paketda (<=20), keyin ataylab replay
        self.assertEqual(len(srv.payloads), 4)
        late, replay = srv.payloads[2], srv.payloads[3]
        self.assertEqual(len(late["readings"]), 4)
        self.assertEqual([r["ts"] for r in late["readings"]], [r["ts"] for r in generated[2:6]])
        self.assertEqual(replay, late)           # bir xil seq va tarkib -> duplicate_batch
        self.assertEqual(dev.stats.duplicates, 1)
        self.assertEqual(dev.pending, [])
        self.assertGreater(late["seq"], srv.payloads[1]["seq"])

    def test_retry_keeps_readings_and_uses_new_seq(self):
        calls = {"n": 0}
        srv = FakeServer()

        def flaky(url, token, payload):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise sim.TransportError("connection refused")
            return srv(url, token, payload)

        dev = make_device(self.tmp, sender=flaky)
        t = sim.utc_now()
        dev.run_cycle(dev.make_readings(t, 1, 15))
        dev.run_cycle(dev.make_readings(t + timedelta(seconds=15), 1, 15))
        self.assertEqual(len(dev.pending), 2)
        dev.run_cycle(dev.make_readings(t + timedelta(seconds=30), 1, 15))
        self.assertEqual(dev.pending, [])
        self.assertEqual(len(srv.payloads), 1)
        self.assertEqual(len(srv.payloads[0]["readings"]), 3)

    def test_large_backlog_split_into_batches_of_20(self):
        srv = FakeServer()
        dev = make_device(self.tmp, sender=srv)
        dev.backfill(hours=6, step_min=10, now=sim.utc_now(), batch=20, pause_s=0)
        sizes = [len(p["readings"]) for p in srv.payloads]
        self.assertEqual(sum(sizes), 37)
        self.assertTrue(all(s <= 20 for s in sizes))
        seqs = [p["seq"] for p in srv.payloads]
        self.assertEqual(seqs, sorted(set(seqs)))
        all_ts = [r["ts"] for p in srv.payloads for r in p["readings"]]
        self.assertEqual(all_ts, sorted(all_ts))
        self.assertLessEqual(all_ts[-1], sim.iso_utc(sim.utc_now()))
        first = datetime.strptime(all_ts[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertGreater(sim.utc_now() - first, timedelta(hours=5, minutes=50))

    def test_auth_error_raises(self):
        dev = make_device(self.tmp, sender=FakeServer(token="other"))
        with self.assertRaises(sim.AuthError):
            dev.run_cycle(dev.make_readings(sim.utc_now(), 1, 15))

    def test_422_dropped_not_retried(self):
        dev = make_device(self.tmp, sender=FakeServer(status=422))
        dev.run_cycle(dev.make_readings(sim.utc_now(), 1, 15))
        self.assertEqual(dev.pending, [])
        self.assertEqual(dev.stats.dropped, 1)


class _Handler(BaseHTTPRequestHandler):
    seen: set = set()
    bodies: list = []

    def log_message(self, *a):  # testlarda shovqin bo'lmasin
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        if self.path != "/api/v1/iot/readings":
            return self._reply(404, {"detail": "Not Found"})
        if self.headers.get("Authorization") != "Bearer sa_good":
            return self._reply(401, {"detail": "Invalid device token"})
        _Handler.bodies.append(body)
        key = (body["device_id"], body["seq"])
        dup = key in _Handler.seen
        _Handler.seen.add(key)
        self._reply(200, {"accepted": 0 if dup else len(body["readings"]),
                          "duplicate_batch": dup, "flagged": 0})

    def _reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class CliHttpTest(unittest.TestCase):
    """Haqiqiy HTTP (127.0.0.1) orqali uchidan-uchiga test."""

    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        _Handler.bodies.clear()

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *extra):
        argv = ["--api", f"http://127.0.0.1:{self.port}/api/v1", "--interval", "0",
                "--state-file", str(self.tmp / "s.json"), "--seed", "1", *extra]
        err, out = io.StringIO(), io.StringIO()
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = sim.main(argv)
        finally:
            sys.stdout, sys.stderr = old
        return code, out.getvalue(), err.getvalue()

    def test_send_ok(self):
        code, out, _ = self._main("--device-id", "esp32-cli", "--token", "sa_good", "--count", "3")
        self.assertEqual(code, 0)
        self.assertEqual(len(_Handler.bodies), 3)
        self.assertIn('"accepted": 1', out)
        for b in _Handler.bodies:
            check_payload_schema(self, b)
        seqs = [b["seq"] for b in _Handler.bodies]
        self.assertEqual(seqs, sorted(set(seqs)))
        # qayta ishga tushirish — seq takrorlanmaydi
        self._main("--device-id", "esp32-cli", "--token", "sa_good", "--count", "1")
        self.assertGreater(_Handler.bodies[-1]["seq"], seqs[-1])

    def test_devices_file_multiple(self):
        f = self.tmp / "devices.json"
        f.write_text(json.dumps([{"device_id": "d-a", "token": "sa_good"},
                                 {"device_id": "d-b", "token": "sa_good", "field_id": 7}]))
        code, _, _ = self._main("--devices-file", str(f), "--count", "2", "--scenario", "drought")
        self.assertEqual(code, 0)
        self.assertEqual(sorted({b["device_id"] for b in _Handler.bodies}), ["d-a", "d-b"])

    def test_auth_error_exit_code(self):
        code, _, err = self._main("--device-id", "esp32-cli", "--token", "sa_bad", "--count", "1")
        self.assertEqual(code, 2)
        self.assertIn("Token yoki device_id noto'g'ri", err)
        self.assertIn("Mini App", err)

    def test_wrong_api_path_exit_code(self):
        code, _, err = self._main("--device-id", "x", "--token", "sa_good", "--count", "1",
                                  "--api", f"http://127.0.0.1:{self.port}/wrong")
        self.assertEqual(code, 3)
        self.assertIn("--api", err)

    def test_server_down_does_not_crash(self):
        code, out, _ = self._main("--device-id", "x", "--token", "sa_good", "--count", "2",
                                  "--api", "http://127.0.0.1:9/api/v1")
        self.assertEqual(code, 0)
        self.assertIn("aloqa yo'q", out)
        self.assertIn("yuborilmay qoldi", out)

    def test_missing_credentials(self):
        code, _, err = self._main("--devices-file", str(self.tmp / "nope.json"), "--count", "1")
        self.assertEqual(code, 3)

    def test_dry_run_prints_payloads(self):
        code, out, _ = self._main("--dry-run", "--count", "2", "--scenario", "heavy_rain",
                                  "--readings-per-post", "3")
        self.assertEqual(code, 0)
        payloads = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
        self.assertEqual(len(payloads), 2)
        for p in payloads:
            check_payload_schema(self, p)
            self.assertEqual(len(p["readings"]), 3)
        self.assertFalse((self.tmp / "s.json").exists(), "dry-run holatni saqlamasligi kerak")
        self.assertEqual(_Handler.bodies, [])

    def test_speed_compresses_model_time(self):
        code, out, _ = self._main("--dry-run", "--count", "1", "--speed", "60",
                                  "--readings-per-post", "20", "--interval", "60")
        # interval=60 → 20 ta o'lchov 3 s oraliqda; speed=60 → model vaqti 3 soat oraliqda
        self.assertEqual(code, 0)
        p = json.loads(next(line for line in out.splitlines() if line.startswith("{")))
        lux = [r["light_lux"] for r in p["readings"]]
        ts = [r["ts"] for r in p["readings"]]
        first = datetime.strptime(ts[0], "%Y-%m-%dT%H:%M:%SZ")
        last = datetime.strptime(ts[-1], "%Y-%m-%dT%H:%M:%SZ")
        self.assertLessEqual(last - first, timedelta(seconds=60))   # ts real vaqt
        self.assertIn(0, lux)                                       # 57 soat model vaqti → tun bor
        self.assertGreater(max(lux), 1000)                          # va kun ham bor


if __name__ == "__main__":
    unittest.main(verbosity=2)
