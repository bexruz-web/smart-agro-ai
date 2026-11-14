"""Smart Agro AI simulyatori uchun testlar.

Ishga tushirish (ikkalasi ham ishlaydi):
    python3 -m pytest simulator/test_sim.py -q
    python3 -m unittest discover -s simulator -p "test_*.py" -v
"""
from __future__ import annotations

import io
import json
import math
import os
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


def make_device(tmp: Path, scenario="normal", sender=None, fmt="readings", **kw) -> sim.VirtualDevice:
    state = sim.StateStore(tmp / "state.json")
    return sim.VirtualDevice("esp32-test", "sa_test", scenario, "http://x/api/v1", state,
                             sender=sender, seed=3, out=io.StringIO(), fmt=fmt, **kw)


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
    paths: list = []

    def log_message(self, *a):  # testlarda shovqin bo'lmasin
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        if self.path not in ("/api/v1/iot/readings", "/api/v1/iot/telemetry"):
            return self._reply(404, {"detail": "Not Found"})
        if self.headers.get("Authorization") != "Bearer sa_good":
            return self._reply(401, {"detail": "Invalid device token"})
        _Handler.paths.append(self.path)
        _Handler.bodies.append(body)
        if self.path.endswith("/telemetry"):
            key = ("t", body["device_id"], body["timestamp"])
            dup = key in _Handler.seen
            _Handler.seen.add(key)
            return self._reply(200, {"accepted": 0 if dup else len(body["measurements"]),
                                     "duplicate": dup, "flagged": 0})
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


class _HttpServerMixin:
    """Lokal HTTP server (127.0.0.1) + sim.main() ni chaqirish yordamchisi."""

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
        _Handler.paths.clear()

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


class CliHttpTest(_HttpServerMixin, unittest.TestCase):
    """Haqiqiy HTTP (127.0.0.1) orqali uchidan-uchiga test (readings + umumiy xatolar)."""

    def test_send_ok(self):
        code, out, _ = self._main("--format", "readings", "--device-id", "esp32-cli", "--token", "sa_good",
                                  "--count", "3")
        self.assertEqual(code, 0)
        self.assertEqual(len(_Handler.bodies), 3)
        self.assertEqual(set(_Handler.paths), {"/api/v1/iot/readings"})
        self.assertIn('"accepted": 1', out)
        for b in _Handler.bodies:
            check_payload_schema(self, b)
        seqs = [b["seq"] for b in _Handler.bodies]
        self.assertEqual(seqs, sorted(set(seqs)))
        # qayta ishga tushirish — seq takrorlanmaydi
        self._main("--format", "readings", "--device-id", "esp32-cli", "--token", "sa_good", "--count", "1")
        self.assertGreater(_Handler.bodies[-1]["seq"], seqs[-1])

    def test_devices_file_multiple(self):
        f = self.tmp / "devices.json"
        f.write_text(json.dumps([{"device_id": "d-a", "token": "sa_good"},
                                 {"device_id": "d-b", "token": "sa_good", "field_id": 7}]))
        code, _, _ = self._main("--format", "readings", "--devices-file", str(f), "--count", "2",
                                "--scenario", "drought")
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
        code, out, _ = self._main("--format", "readings", "--device-id", "esp32-dry", "--dry-run",
                                  "--count", "2", "--scenario", "heavy_rain", "--readings-per-post", "3")
        self.assertEqual(code, 0)
        payloads = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
        self.assertEqual(len(payloads), 2)
        for p in payloads:
            check_payload_schema(self, p)
            self.assertEqual(len(p["readings"]), 3)
        self.assertFalse((self.tmp / "s.json").exists(), "dry-run holatni saqlamasligi kerak")
        self.assertEqual(_Handler.bodies, [])

    def test_speed_compresses_model_time(self):
        code, out, _ = self._main("--format", "readings", "--device-id", "esp32-dry", "--dry-run",
                                  "--count", "1", "--speed", "60", "--readings-per-post", "20",
                                  "--interval", "60")
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


# =========================================================================== telemetry
TELEMETRY_TOP_KEYS = {"device_id", "timestamp", "measurements", "status"}
STATUS_KEYS = {"signal_quality", "sensor_errors", "simulated"}
ALL_T = set(sim.TELEMETRY_KEYS)


def check_telemetry_schema(tc: unittest.TestCase, p: dict) -> None:
    """docs/API_CONTRACT_V2.md "Datchik telemetriyasi" bo'yicha."""
    tc.assertEqual(set(p), TELEMETRY_TOP_KEYS)
    tc.assertIsInstance(p["device_id"], str)
    tc.assertRegex(p["timestamp"], TS_RE)
    ms, st = p["measurements"], p["status"]
    tc.assertTrue(set(ms) <= ALL_T, set(ms) - ALL_T)
    for k, m in ms.items():
        tc.assertEqual(set(m), {"value", "unit"})
        tc.assertEqual(m["unit"], sim.TELEMETRY_UNITS[k])
        tc.assertIsInstance(m["value"], (int, float))
        tc.assertNotIsInstance(m["value"], bool)
        tc.assertTrue(math.isfinite(m["value"]))
    tc.assertTrue(set(st) <= STATUS_KEYS, set(st) - STATUS_KEYS)
    tc.assertIsInstance(st["sensor_errors"], list)
    if "signal_quality" in st:
        tc.assertIsInstance(st["signal_quality"], int)
        tc.assertTrue(0 <= st["signal_quality"] <= sim.CSQ_MAX)
    errs = set(st["sensor_errors"])
    tc.assertTrue(errs <= ALL_T)
    tc.assertFalse(errs & set(ms), "ishlamayotgan datchik qiymati yuborilmasligi kerak")
    tc.assertEqual(set(ms) | errs, ALL_T, "har bir o'lchov yo qiymat bilan, yo sensor_errors'da bo'lishi kerak")
    json.dumps(p, allow_nan=False)


def tseries(scenario: str, hours: float = 24, step_min: float = 15, start: datetime = T0, seed: int = 42,
            elevation: float = sim.DEFAULT_ELEVATION_M, mm_per_tip: float = sim.RAIN_MM_PER_TIP):
    m = sim.TelemetryModel(scenario=scenario, seed=seed, lat=LAT, lon=LON, elevation_m=elevation,
                           mm_per_tip=mm_per_tip, first_interval_s=step_min * 60)
    n = int(hours * 60 / step_min)
    out = []
    for i in range(n):
        ts = start + timedelta(minutes=step_min * i)
        values, errors = m.next_values(ts)
        out.append((ts, values, errors))
    return out, m


def tlive(scenario: str, n: int = 20, seed: int = 7, interval_s: float = 15):
    m = sim.TelemetryModel(scenario=scenario, seed=seed, lat=LAT, lon=LON, first_interval_s=interval_s)
    t = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    return [m.next_values(t + timedelta(seconds=interval_s * i)) for i in range(n)]


def is_multiple(v: float, step: float) -> bool:
    return abs(v / step - round(v / step)) < 1e-6


class TelemetryModelTest(unittest.TestCase):
    def test_normal_value_ranges(self):
        for start in (T0, SUMMER_T0):
            rows, _ = tseries("normal", hours=48, start=start)
            for _, v, errs in rows:
                self.assertEqual(errs, [])
                self.assertEqual(set(v), ALL_T)
                self.assertTrue(0 <= v["soil_moisture"] <= 60)
                self.assertTrue(-10 <= v["soil_temperature"] <= 45)
                self.assertTrue(-30 <= v["air_temperature"] <= 50)
                self.assertTrue(0 <= v["air_humidity"] <= 100)
                # 380 m: dengiz sathi 993..1037 hPa (mavsum ± sinoptik) x 0.9555
                self.assertTrue(945 <= v["air_pressure"] <= 995, v["air_pressure"])
                self.assertTrue(0 <= v["light_intensity"] <= sim.BH1750_MAX_LUX)
                self.assertIsInstance(v["light_intensity"], int)
                self.assertEqual(v["rainfall"], 0)

    def test_pressure_follows_elevation(self):
        means = {}
        for elev, lo, hi in ((0, 990, 1040), (380, 945, 995), (1000, 878, 923)):
            for start in (T0, SUMMER_T0):
                rows, _ = tseries("normal", hours=72, start=start, elevation=elev)
                ps = [v["air_pressure"] for _, v, _ in rows]
                self.assertTrue(lo <= min(ps) and max(ps) <= hi, (elev, min(ps), max(ps)))
                means.setdefault(elev, []).extend(ps)
        m0, m1000 = (sum(means[e]) / len(means[e]) for e in (0, 1000))
        self.assertTrue(100 < m0 - m1000 < 125, m0 - m1000)
        self.assertAlmostEqual(sim.station_pressure_hpa(1013.25, 0), 1013.25)
        self.assertAlmostEqual(sim.station_pressure_hpa(1013.25, 1000), 898.7, delta=0.5)

    def test_pressure_scenarios(self):
        def mean_p(sc):
            rows = tlive(sc, n=30, interval_s=300)
            return sum(v["air_pressure"] for v, _ in rows[10:]) / 20
        normal = mean_p("normal")
        self.assertLess(mean_p("heavy_rain"), normal - 5)     # siklon
        self.assertGreater(mean_p("frost"), normal + 4)       # antisiklon

    def test_light_zero_at_night_and_bh1750_cap(self):
        rows, _ = tseries("normal", hours=24, start=SUMMER_T0)
        night = [v["light_intensity"] for ts, v, _ in rows
                 if sim.solar_hour(ts, LON) < 4.5 or sim.solar_hour(ts, LON) > 20]
        noon = [v["light_intensity"] for ts, v, _ in rows if 11.5 <= sim.solar_hour(ts, LON) <= 12.5]
        self.assertTrue(night and all(x == 0 for x in night))
        self.assertTrue(noon and min(noon) > 30000)
        self.assertTrue(max(noon) <= sim.BH1750_MAX_LUX)

    def test_ds18b20_resolution(self):
        rows, _ = tseries("normal", hours=6)
        for _, v, _ in rows:
            q = v["soil_temperature"] / sim.DS18B20_STEP_C
            self.assertLess(abs(q - round(q)), 0.1)          # 0.0625 °C qadam (2 xonagacha yaxlitlangan)

    def test_heavy_rain_tipping_bucket(self):
        rows = tlive("heavy_rain", n=24, interval_s=300)       # 2 soat, har 5 daqiqada paket
        rain = [v["rainfall"] for v, _ in rows]
        self.assertTrue(all(is_multiple(r, 0.2) for r in rain), rain)
        self.assertTrue(all(r > 0 for r in rain[2:]))
        self.assertTrue(20 < sum(rain) < 90, sum(rain))         # ~25–30 mm/soat
        self.assertTrue(max(rain) < 10)
        self.assertGreater(rows[-1][0]["air_humidity"], 85)
        self.assertGreaterEqual(rows[-1][0]["soil_moisture"], 40)

    def test_rain_is_conserved(self):
        m = sim.TelemetryModel("heavy_rain", seed=3, first_interval_s=60)
        t = T0
        total = 0.0
        for i in range(120):
            total += m.next_values(t + timedelta(minutes=i))[0]["rainfall"]
        self.assertAlmostEqual(total, m.total_tips * sim.RAIN_MM_PER_TIP, places=6)
        self.assertTrue(0 <= m.bucket_mm < sim.RAIN_MM_PER_TIP)

    def test_rain_live_interval_small_amounts(self):
        rain = [v["rainfall"] for v, _ in tlive("heavy_rain", n=40, interval_s=15)]
        self.assertTrue(set(rain) <= {0.0, 0.2, 0.4})
        self.assertGreaterEqual(rain.count(0.2), 5)

    def test_mm_per_tip_parameter(self):
        rows, _ = tseries("heavy_rain", hours=2, step_min=5, mm_per_tip=0.5)
        rain = [v["rainfall"] for _, v, _ in rows]
        self.assertTrue(all(is_multiple(r, 0.5) for r in rain))
        self.assertGreater(sum(rain), 0)

    def test_no_rain_in_dry_scenarios(self):
        for sc in ("normal", "drought", "frost", "sensor_fault", "offline"):
            rows, _ = tseries(sc, hours=12)
            self.assertTrue(all(v.get("rainfall") == 0 for _, v, _ in rows), sc)

    def test_sensor_fault_omits_sensor_and_one_spike(self):
        rows = tlive("sensor_fault", n=20)
        for i, (v, errs) in enumerate(rows):
            if i < sim.FAULT_START_STEP:
                self.assertEqual(errs, [])
                self.assertIn("soil_temperature", v)
            else:
                self.assertEqual(errs, [sim.FAULT_MISSING_METRIC])
                self.assertNotIn(sim.FAULT_MISSING_METRIC, v)
            self.assertEqual(set(v) | set(errs), ALL_T)
        spikes = [i for i, (v, _) in enumerate(rows) if v["air_temperature"] >= 80]
        self.assertEqual(spikes, [sim.FAULT_SPIKE_FIRST])
        self.assertEqual(rows[sim.FAULT_SPIKE_FIRST][0]["air_temperature"], sim.FAULT_SPIKE_VALUE)
        soil = [v["soil_moisture"] for v, _ in rows]
        self.assertGreater(len(set(soil[sim.FAULT_START_STEP:])), 1, "telemetriyada namlik qotmaydi")

    def test_drought_and_frost(self):
        dry = [v["soil_moisture"] for v, _ in tlive("drought", n=20)]
        self.assertLess(dry[-1], 15.0)
        rows, _ = tseries("frost", hours=36)
        nights = [v["air_temperature"] for ts, v, _ in rows[sim.RAMP_STEPS:]
                  if sim.solar_hour(ts, LON) < 8 or sim.solar_hour(ts, LON) > 20]
        self.assertLess(min(nights), 0.0)

    def test_seed_reproducible(self):
        a = [v for _, v, _ in tseries("heavy_rain", hours=2, seed=5)[0]]
        b = [v for _, v, _ in tseries("heavy_rain", hours=2, seed=5)[0]]
        c = [v for _, v, _ in tseries("heavy_rain", hours=2, seed=6)[0]]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_csq_mapping(self):
        self.assertEqual(sim.csq_from_rssi(-113), 0)
        self.assertEqual(sim.csq_from_rssi(-51), 31)
        self.assertEqual(sim.csq_from_rssi(-40), 31)
        self.assertEqual(sim.csq_from_rssi(-77), 18)


class FakeTelemetryServer:
    """Kontrakt bo'yicha: (device_id, timestamp) takrorlansa duplicate=true."""

    def __init__(self, token="sa_test", status=200):
        self.token = token
        self.status = status
        self.payloads: list[dict] = []
        self.urls: list[str] = []
        self.seen: set = set()

    def __call__(self, url, token, payload):
        if token != self.token:
            return 401, {"detail": "Noto'g'ri qurilma tokeni"}
        if self.status != 200:
            return self.status, {"detail": "xato"}
        self.urls.append(url)
        self.payloads.append(json.loads(json.dumps(payload)))
        key = (payload["device_id"], payload["timestamp"])
        dup = key in self.seen
        self.seen.add(key)
        flagged = sum(1 for k, m in payload["measurements"].items()
                      if k == "air_temperature" and not -40 <= m["value"] <= 55)
        return 200, {"accepted": 0 if dup else len(payload["measurements"]), "duplicate": dup,
                     "flagged": 0 if dup else flagged}


def make_tdevice(tmp: Path, scenario="normal", sender=None, **kw) -> sim.VirtualDevice:
    return make_device(tmp, scenario=scenario, sender=sender, fmt="telemetry", **kw)


class TelemetryDeviceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_contract_example_shape(self):
        ts = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
        p = sim.build_telemetry_payload("SMARTAGRO-ESP32-001", ts, {
            "soil_moisture": 34.5, "soil_temperature": 21.4, "air_temperature": 27.2, "air_humidity": 48.5,
            "air_pressure": 1012.5, "light_intensity": 12500, "rainfall": 0.2}, 18, [], simulated=False)
        self.assertEqual(p, {
            "device_id": "SMARTAGRO-ESP32-001", "timestamp": "2026-11-14T10:00:00Z",
            "measurements": {
                "soil_moisture": {"value": 34.5, "unit": "%"}, "soil_temperature": {"value": 21.4, "unit": "C"},
                "air_temperature": {"value": 27.2, "unit": "C"}, "air_humidity": {"value": 48.5, "unit": "%"},
                "air_pressure": {"value": 1012.5, "unit": "hPa"}, "light_intensity": {"value": 12500, "unit": "lux"},
                "rainfall": {"value": 0.2, "unit": "mm"}},
            "status": {"signal_quality": 18, "sensor_errors": []}})
        check_telemetry_schema(self, p)
        q = sim.build_telemetry_payload("d", ts, {"soil_moisture": 30.0}, None,
                                        [k for k in sim.TELEMETRY_KEYS if k != "soil_moisture"])
        self.assertNotIn("signal_quality", q["status"])
        self.assertTrue(q["status"]["simulated"])
        check_telemetry_schema(self, q)
        with self.assertRaises(ValueError):
            sim.build_telemetry_payload("d", ts, {"wind_speed": 3.0}, 10, [])

    def test_packets_schema_url_and_unique_timestamps(self):
        srv = FakeTelemetryServer()
        dev = make_tdevice(self.tmp, sender=srv)
        t = sim.utc_now()
        for _ in range(5):                       # bir xil soniya -> timestamp baribir o'sadi
            dev.telemetry_cycle(t)
        self.assertEqual(len(srv.payloads), 5)
        self.assertTrue(all(u == "http://x/api/v1/iot/telemetry" for u in srv.urls))
        tss = [p["timestamp"] for p in srv.payloads]
        self.assertEqual(tss, sorted(set(tss)))
        for p in srv.payloads:
            check_telemetry_schema(self, p)
            self.assertEqual(p["device_id"], "esp32-test")
            self.assertTrue(p["status"]["simulated"])
        self.assertEqual(dev.stats.accepted, 35)
        self.assertEqual(dev.stats.duplicates, 0)

    def test_sensor_fault_is_flagged_by_server(self):
        srv = FakeTelemetryServer()
        dev = make_tdevice(self.tmp, scenario="sensor_fault", sender=srv)
        t = sim.utc_now()
        for i in range(8):
            dev.telemetry_cycle(t + timedelta(seconds=15 * i))
        errs = [p["status"]["sensor_errors"] for p in srv.payloads]
        self.assertEqual(errs[:3], [[], [], []])
        self.assertTrue(all(e == ["soil_temperature"] for e in errs[3:]))
        self.assertEqual(dev.stats.flagged, 1)

    def test_offline_buffers_then_flushes_with_original_ts_and_duplicate(self):
        srv = FakeTelemetryServer()
        dev = make_tdevice(self.tmp, scenario="offline", sender=srv, offline_batches=3, online_batches=2)
        base = sim.utc_now() - timedelta(minutes=10)
        generated = []
        for i in range(6):                       # 2 online, 3 offline, 1 flush
            generated.append(dev.telemetry_cycle(base + timedelta(seconds=15 * i)))
            if i < 2:
                self.assertEqual(len(srv.payloads), i + 1)
            elif i < 5:
                self.assertEqual(len(srv.payloads), 2, "offline paytida yuborilmasligi kerak")
        # flush: 3 ta buferdagi + 1 joriy (bittadan), keyin ataylab takroriy paket
        self.assertEqual(len(srv.payloads), 7)
        sent_ts = [p["timestamp"] for p in srv.payloads[2:6]]
        self.assertEqual(sent_ts, [g["timestamp"] for g in generated[2:6]])
        self.assertEqual(srv.payloads[6], srv.payloads[5])
        self.assertEqual(dev.stats.duplicates, 1)
        self.assertEqual(dev.pending, [])
        for g in generated[2:5]:
            self.assertLessEqual(g["status"]["signal_quality"], 5)   # aloqa yo'q paytdagi signal

    def test_retry_keeps_packets_in_order(self):
        calls = {"n": 0}
        srv = FakeTelemetryServer()

        def flaky(url, token, payload):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise sim.TransportError("connection refused")
            return srv(url, token, payload)

        dev = make_tdevice(self.tmp, sender=flaky)
        t = sim.utc_now()
        a = dev.telemetry_cycle(t)
        b = dev.telemetry_cycle(t + timedelta(seconds=15))
        self.assertEqual(dev.pending, [a, b])
        c = dev.telemetry_cycle(t + timedelta(seconds=30))
        self.assertEqual(dev.pending, [])
        self.assertEqual([p["timestamp"] for p in srv.payloads], [a["timestamp"], b["timestamp"], c["timestamp"]])

    def test_queue_is_bounded(self):
        def down(url, token, payload):
            raise sim.TransportError("no network")

        dev = make_tdevice(self.tmp, sender=down)
        t = sim.utc_now() - timedelta(hours=10)
        gen = [dev.telemetry_cycle(t + timedelta(minutes=5 * i)) for i in range(sim.TELEMETRY_QUEUE_MAX + 10)]
        self.assertEqual(len(dev.pending), sim.TELEMETRY_QUEUE_MAX)
        self.assertEqual(dev.pending[0]["timestamp"], gen[10]["timestamp"])   # eng eskilari tashlandi
        self.assertEqual(dev.stats.dropped, 10)

    def test_backfill_one_post_per_packet(self):
        srv = FakeTelemetryServer()
        dev = make_tdevice(self.tmp, sender=srv)
        dev.backfill(hours=2, step_min=10, now=sim.utc_now(), batch=20, pause_s=0)
        self.assertEqual(len(srv.payloads), 13)
        tss = [p["timestamp"] for p in srv.payloads]
        self.assertEqual(tss, sorted(set(tss)))
        for p in srv.payloads:
            check_telemetry_schema(self, p)

    def test_error_handling(self):
        dev = make_tdevice(self.tmp, sender=FakeTelemetryServer(token="other"))
        with self.assertRaises(sim.AuthError):
            dev.telemetry_cycle(sim.utc_now())
        dev = make_tdevice(self.tmp, sender=FakeTelemetryServer(status=422))
        dev.telemetry_cycle(sim.utc_now())
        self.assertEqual(dev.pending, [])
        self.assertEqual(dev.stats.dropped, 1)
        for code in (404, 405):
            dev = make_tdevice(self.tmp, sender=FakeTelemetryServer(status=code))
            with self.assertRaises(sim.ConfigError):
                dev.telemetry_cycle(sim.utc_now())
        dev = make_tdevice(self.tmp, sender=FakeTelemetryServer(status=503))
        dev.telemetry_cycle(sim.utc_now())
        self.assertEqual(len(dev.pending), 1)


class TelemetryCliTest(_HttpServerMixin, unittest.TestCase):
    """Haqiqiy HTTP orqali: default format = telemetry."""

    def test_send_ok(self):
        code, out, _ = self._main("--device-id", "esp32-cli", "--token", "sa_good", "--count", "3")
        self.assertEqual(code, 0)
        self.assertEqual(_Handler.paths, ["/api/v1/iot/telemetry"] * 3)
        self.assertIn('"accepted": 7', out)
        self.assertIn("duplicate=0", out)
        for b in _Handler.bodies:
            check_telemetry_schema(self, b)
        tss = [b["timestamp"] for b in _Handler.bodies]
        self.assertEqual(tss, sorted(set(tss)))

    def test_offline_cli_duplicate(self):
        code, out, _ = self._main("--device-id", "esp32-off", "--token", "sa_good", "--count", "5",
                                  "--scenario", "offline", "--offline-batches", "2")
        self.assertEqual(code, 0)
        self.assertIn("duplicate=1", out)
        self.assertEqual(len(_Handler.bodies), 6)      # 2 + (2 bufer + 1 joriy) + 1 takroriy

    def test_dry_run_elevation(self):
        def pressures(elev):
            code, out, _ = self._main("--device-id", "esp32-dry", "--dry-run", "--count", "3",
                                      "--elevation", str(elev))
            self.assertEqual(code, 0)
            ps = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
            self.assertEqual(len(ps), 3)
            for p in ps:
                check_telemetry_schema(self, p)
            return [p["measurements"]["air_pressure"]["value"] for p in ps]
        self.assertTrue(all(985 < v < 1045 for v in pressures(0)))
        self.assertTrue(all(880 < v < 930 for v in pressures(1000)))
        self.assertEqual(_Handler.bodies, [])

    def test_dry_run_sensor_fault(self):
        code, out, _ = self._main("--device-id", "esp32-dry", "--dry-run", "--count", "8",
                                  "--scenario", "sensor_fault")
        self.assertEqual(code, 0)
        ps = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
        self.assertEqual([p["status"]["sensor_errors"] for p in ps[:3]], [[], [], []])
        self.assertTrue(all(p["status"]["sensor_errors"] == ["soil_temperature"] for p in ps[3:]))
        spikes = [p for p in ps if p["measurements"]["air_temperature"]["value"] >= 80]
        self.assertEqual(len(spikes), 1)

    def test_args_validation_and_defaults(self):
        old = os.environ.pop("SIM_API", None)
        try:
            a = sim.parse_args([])
        finally:
            if old is not None:
                os.environ["SIM_API"] = old
        self.assertEqual(a.api, "http://localhost:8088/api/v1")
        self.assertEqual(a.format, "telemetry")
        err = io.StringIO()
        old_err, sys.stderr = sys.stderr, err
        try:
            for bad in (["--readings-per-post", "3"], ["--elevation", "9000"], ["--mm-per-tip", "0"],
                        ["--format", "xml"]):
                with self.assertRaises(SystemExit):
                    sim.parse_args(bad)
        finally:
            sys.stderr = old_err
        self.assertEqual(sim.parse_args(["--format", "readings", "--readings-per-post", "3"]).readings_per_post, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
