#!/usr/bin/env python3
"""Smart Agro AI — virtual IoT sensor simulator.

Real ESP32 qurilmasi bilan bir xil API'dan foydalanadi:
    POST {api}/iot/readings   Authorization: Bearer <device_token>

Faqat Python standart kutubxonasi (3.10+), tashqi bog'liqliklar yo'q.

Misollar:
    python3 simulator/sim.py --scenario drought
    python3 simulator/sim.py --device-id esp32-7f3a --token sa_xxx --scenario frost
    python3 simulator/sim.py --dry-run --count 3 --interval 0
    python3 simulator/sim.py --scenario normal --backfill-hours 24 --count 0
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

FW_VERSION = "0.1.0-sim"
SCENARIOS = ("normal", "drought", "heavy_rain", "frost", "sensor_fault", "offline")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DEVICES_FILE = SCRIPT_DIR / "devices.json"
DEFAULT_STATE_FILE = SCRIPT_DIR / ".state.json"
DEFAULT_API = "http://localhost:8000/api/v1"
MAX_READINGS_PER_POST = 20          # firmware bilan bir xil
PENDING_MAX = 5000                  # qayta yuborish navbati limiti

# Firmware'dagi default kalibrlash (config.example.h) — xom ADC qiymatini tiklash uchun
SOIL_ADC_DRY = 2950
SOIL_ADC_WET = 1250
SOIL_VWC_AT_WET = 50.0
SOIL_VWC_MAX = 60.0

RAMP_STEPS = 6                      # ssenariy to'liq kuchga necha o'lchovda chiqadi
FAULT_START_STEP = 3                # sensor_fault: namlik shu qadamdan "qotadi"
FAULT_SPIKE_FIRST = 5               # sensor_fault: 85 °C sakrash qadamlari 5, 11, 17, ...
FAULT_SPIKE_EVERY = 6
FAULT_SPIKE_VALUE = 85.0

READING_KEYS = (
    "ts", "soil_moisture_raw", "soil_moisture_vwc", "soil_temp_c",
    "air_temp_c", "air_rh", "rain", "light_lux",
)


class AuthError(Exception):
    """401/403 — token yoki device_id noto'g'ri."""


class ConfigError(Exception):
    """Noto'g'ri sozlama (masalan, endpoint topilmadi)."""


class TransportError(Exception):
    """Tarmoq xatosi (server ishlamayapti, timeout ...)."""


# --------------------------------------------------------------------------- vaqt
def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def solar_hour(t: datetime, lon: float) -> float:
    """Mahalliy quyosh vaqti (soat, 0..24)."""
    t = t.astimezone(timezone.utc)
    h = t.hour + t.minute / 60 + t.second / 3600
    return (h + lon / 15.0) % 24.0


def solar_elevation_deg(t: datetime, lat: float, lon: float) -> float:
    t = t.astimezone(timezone.utc)
    doy = t.timetuple().tm_yday
    b = math.radians(360.0 / 365.0 * (doy - 81))
    decl = math.radians(23.44) * math.sin(b)
    eot_min = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    st = solar_hour(t, lon) + eot_min / 60.0
    ha = math.radians(15.0 * (st - 12.0))
    phi = math.radians(lat)
    s = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(ha)
    return math.degrees(math.asin(max(-1.0, min(1.0, s))))


def diurnal_shape(h: float) -> float:
    """-1 (≈06:00, quyosh chiqishi) … +1 (≈15:00) asimmetrik sutkalik egri chiziq."""
    if 6.0 <= h < 15.0:
        return -math.cos(math.pi * (h - 6.0) / 9.0)
    hh = (h - 15.0) % 24.0          # 0..15 soat sovish
    return math.cos(math.pi * hh / 15.0)


def climate_normals(t: datetime) -> tuple[float, float, float]:
    """(o'rtacha sutkalik harorat °C, sutkalik amplituda °C, o'rtacha RH %) — O'zbekiston tekisligi uchun taxminiy."""
    doy = t.timetuple().tm_yday
    c = math.cos(2 * math.pi * (doy - 200) / 365.0)   # +1 iyul, -1 yanvar
    return 14.5 + 13.5 * c, 6.5 + 1.5 * c, 55.0 - 20.0 * c


def vwc_to_raw(vwc: float) -> int:
    """Firmware formulasi teskarisi: VWC% -> xom ADC."""
    raw = SOIL_ADC_DRY - (vwc / SOIL_VWC_AT_WET) * (SOIL_ADC_DRY - SOIL_ADC_WET)
    return int(round(max(0, min(4095, raw))))


# --------------------------------------------------------------------------- model
@dataclass
class FieldModel:
    """Bitta dala nuqtasining fizik-ga o'xshash modeli + ssenariy ta'siri."""

    scenario: str = "normal"
    seed: Optional[int] = None
    lat: float = 40.12
    lon: float = 67.84
    rng: random.Random = field(init=False)
    theta: float = field(init=False)                 # tuproq namligi, VWC %
    soil_t: Optional[float] = field(init=False, default=None)
    step: int = field(init=False, default=0)
    cloud: float = field(init=False, default=0.85)
    stuck_vwc: Optional[float] = field(init=False, default=None)
    stuck_raw: Optional[int] = field(init=False, default=None)
    last_model_time: Optional[datetime] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.scenario not in SCENARIOS:
            raise ValueError(f"noma'lum ssenariy: {self.scenario}")
        self.rng = random.Random(self.seed)
        start = {"normal": 27.0, "drought": 21.0, "heavy_rain": 22.0, "frost": 30.0,
                 "sensor_fault": 26.0, "offline": 27.0}[self.scenario]
        self.theta = start + self.rng.uniform(-1.0, 1.0)

    # ssenariy intensivligi 0..1
    def intensity(self) -> float:
        return min(1.0, self.step / RAMP_STEPS)

    def air(self, mt: datetime, s: float) -> tuple[float, float]:
        mean, amp, rh_mean = climate_normals(mt)
        if self.scenario == "drought":
            mean += 9.0 * s
            amp += 2.0 * s
        elif self.scenario == "frost":
            # radiatsion sovuq: kunduzi ~+3 °C, tunda ~-7 °C
            mean += (-2.0 - mean) * s
            amp += (5.0 - amp) * s
        elif self.scenario == "heavy_rain":
            mean -= 3.0 * s
            amp *= 1.0 - 0.6 * s
        t_air = mean + amp * diurnal_shape(solar_hour(mt, self.lon))
        rh = rh_mean - 3.0 * (t_air - mean)
        if self.scenario == "drought":
            rh *= 1.0 - 0.55 * s
        elif self.scenario == "heavy_rain":
            rh += (96.0 - rh) * s
        elif self.scenario == "frost":
            rh += (85.0 - rh) * s * 0.5
        return t_air, max(5.0, min(100.0, rh))

    def next_reading(self, ts: datetime, model_time: Optional[datetime] = None) -> dict:
        """Bitta o'lchov (kontraktdagi kalitlar bilan). ts — yuboriladigan vaqt belgisi."""
        mt = model_time or ts
        dt_h = 0.0
        if self.last_model_time is not None:
            dt_h = max(0.0, (mt - self.last_model_time).total_seconds() / 3600.0)
        self.last_model_time = mt
        s = self.intensity()
        rng = self.rng

        # bulutlilik (sekin tasodifiy yurish)
        if self.scenario == "heavy_rain":
            self.cloud = 0.15 + 0.05 * rng.random()
        elif self.scenario in ("drought", "frost"):
            self.cloud = 0.97
        else:
            self.cloud = max(0.45, min(1.0, self.cloud + rng.gauss(0, 0.04)))

        t_air, rh = self.air(mt, s)
        t_air += rng.gauss(0, 0.15)
        rh = max(5.0, min(100.0, rh + rng.gauss(0, 1.0)))

        elev = solar_elevation_deg(mt, self.lat, self.lon)
        if elev <= 0:
            lux = 0.0
        else:
            lux = 120000.0 * math.sin(math.radians(elev)) ** 1.25 * self.cloud
            lux *= 1.0 + rng.gauss(0, 0.03)
        lux = max(0.0, lux)

        # tuproq harorati havo haroratidan kechikadi (1-tartibli filtr, tau ~8 soat)
        mean, _, _ = climate_normals(mt)
        if self.soil_t is None:
            if self.scenario == "frost":
                mean = 3.0
            self.soil_t = mean + 1.0
        if dt_h > 0:
            k = 1.0 - math.exp(-dt_h / 8.0)
            self.soil_t += (t_air - self.soil_t) * k
        if self.scenario == "frost":
            self.soil_t -= 0.35 * s            # demo: tuproq ham sovib boradi
            self.soil_t = max(self.soil_t, -2.0)

        # tuproq namligi: evapotranspiratsiya + drenaj + ssenariy majburlashi
        et_mm_h = (lux / 100000.0) * (0.25 + 0.02 * max(t_air, 0.0)) * (2.0 - rh / 100.0)
        if self.scenario == "drought":
            et_mm_h *= 1.0 + 0.8 * s
        et_mm_h *= min(1.0, self.theta / 15.0)               # suv stressi
        self.theta -= et_mm_h * dt_h / 300.0 * 100.0           # 30 cm ildiz zonasi
        if self.theta > 34.0:                                  # dala nam sig'imidan ortig'i drenajlanadi
            self.theta -= (self.theta - 34.0) * (1.0 - math.exp(-0.08 * dt_h))
        rain = False
        if self.scenario == "drought":
            self.theta -= 1.3 * s
            self.theta = max(self.theta, 6.0)
        elif self.scenario == "heavy_rain":
            rain = True
            self.theta = min(self.theta + 3.0 * s, 46.0 + rng.uniform(0, 2.0))
        self.theta = max(2.0, min(SOIL_VWC_MAX, self.theta))

        vwc = max(0.0, min(SOIL_VWC_MAX, self.theta + rng.gauss(0, 0.2)))
        raw = vwc_to_raw(vwc) + int(rng.gauss(0, 6))

        if self.scenario == "sensor_fault" and self.step >= FAULT_START_STEP:
            if self.stuck_vwc is None:
                self.stuck_vwc, self.stuck_raw = round(vwc, 1), raw
            vwc, raw = self.stuck_vwc, self.stuck_raw          # qotib qolgan qiymat
            n = self.step - FAULT_SPIKE_FIRST
            if n >= 0 and n % FAULT_SPIKE_EVERY == 0:
                t_air = FAULT_SPIKE_VALUE                       # diapazondan tashqari sakrash

        self.step += 1
        return {
            "ts": iso_utc(ts),
            "soil_moisture_raw": int(max(0, min(4095, raw))),
            "soil_moisture_vwc": round(vwc, 1),
            "soil_temp_c": round(self.soil_t + rng.gauss(0, 0.05), 2),
            "air_temp_c": round(t_air, 1),
            "air_rh": round(rh, 1),
            "rain": rain,
            "light_lux": int(round(lux)),
        }


# --------------------------------------------------------------------------- payload
def build_payload(device_id: str, seq: int, readings: list[dict], rssi: int,
                  battery_v: Optional[float], fw: str = FW_VERSION) -> dict:
    payload = {"device_id": device_id, "fw": fw, "seq": seq, "rssi": rssi}
    if battery_v is not None:
        payload["battery_v"] = round(battery_v, 2)
    payload["readings"] = readings
    return payload


# --------------------------------------------------------------------------- holat
class StateStore:
    """Har bir qurilma uchun seq'ni JSON faylda saqlaydi (qayta ishga tushganda takrorlanmaydi)."""

    def __init__(self, path: Path, persist: bool = True):
        self.path = Path(path)
        self.persist = persist
        self.data: dict = {"devices": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.setdefault("devices", {})
            except (OSError, json.JSONDecodeError):
                print(f"OGOHLANTIRISH: {self.path} o'qilmadi, yangi holat yaratiladi", file=sys.stderr)

    def next_seq(self, device_id: str) -> int:
        dev = self.data["devices"].setdefault(device_id, {})
        last = int(dev.get("seq", 0))
        if last <= 0:
            # Holat fayli yo'q bo'lsa — Unix vaqtidan boshlaymiz (firmware kabi), shunda
            # .state.json o'chirilsa ham server eski seq bilan to'qnashmaydi.
            last = int(time.time())
        seq = last + 1
        dev["seq"] = seq
        dev["updated_at"] = iso_utc(utc_now())
        self.save()
        return seq

    def save(self) -> None:
        if not self.persist:
            return
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)


# --------------------------------------------------------------------------- HTTP
def http_post_json(url: str, token: str, payload: dict, timeout: float = 15.0) -> tuple[int, object]:
    body = json.dumps(payload, allow_nan=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": f"smart-agro-sim/{FW_VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, text = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise TransportError(str(reason)) from e
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError:
        return status, text


Sender = Callable[[str, str, dict], "tuple[int, object]"]


# --------------------------------------------------------------------------- qurilma
@dataclass
class Stats:
    posts: int = 0
    ok: int = 0
    accepted: int = 0
    duplicates: int = 0
    flagged: int = 0
    errors: int = 0
    dropped: int = 0


class VirtualDevice:
    def __init__(self, device_id: str, token: str, scenario: str, api: str, state: StateStore,
                 sender: Optional[Sender] = None, dry_run: bool = False, seed: Optional[int] = None,
                 lat: float = 40.12, lon: float = 67.84, offline_batches: int = 4,
                 online_batches: int = 2, out=None, pretty: bool = False):
        self.device_id = device_id
        self.token = token
        self.scenario = scenario
        self.url = api.rstrip("/") + "/iot/readings"
        self.state = state
        self.sender = sender or (lambda url, tok, p: http_post_json(url, tok, p))
        self.dry_run = dry_run
        self.rng = random.Random(None if seed is None else seed + 7919)
        self.model = FieldModel(scenario=scenario, seed=seed, lat=lat, lon=lon)
        self.offline_batches = max(1, offline_batches)
        self.online_batches = max(1, online_batches)
        self.pending: list[dict] = []
        self.cycle = 0
        self.was_offline = False
        self.last_payload: Optional[dict] = None
        self.rssi = -68.0
        self.stats = Stats()
        self.out = out or sys.stdout
        self.pretty = pretty

    # ---- yordamchi
    def log(self, msg: str) -> None:
        print(f"{iso_utc(utc_now())} [{self.device_id}] {msg}", file=self.out, flush=True)

    def _rssi(self) -> int:
        self.rssi = max(-95.0, min(-45.0, self.rssi + self.rng.gauss(0, 2.0)))
        return int(round(self.rssi))

    def _battery(self, readings: list[dict]) -> float:
        lux = readings[-1].get("light_lux", 0) if readings else 0
        return 3.72 + 0.35 * min(1.0, lux / 100000.0) + self.rng.gauss(0, 0.01)

    def is_offline_cycle(self, cycle: int) -> bool:
        if self.scenario != "offline":
            return False
        period = self.online_batches + self.offline_batches
        return (cycle % period) >= self.online_batches

    # ---- o'lchovlar
    def make_readings(self, t_end: datetime, k: int, span_s: float,
                      model_time: Callable[[datetime], datetime] = lambda t: t) -> list[dict]:
        """t_end gacha k ta o'lchov (oraliq span_s/k), vaqt bo'yicha o'sib boruvchi."""
        k = max(1, k)
        step = span_s / k if k > 1 else 0.0
        out = []
        for j in range(k):
            ts = t_end - timedelta(seconds=step * (k - 1 - j))
            ts = ts.replace(microsecond=0)
            out.append(self.model.next_reading(ts, model_time(ts)))
        return out

    # ---- yuborish
    def _post(self, payload: dict) -> str:
        """'ok' | 'retry' | 'drop'. AuthError/ConfigError yuqoriga uzatiladi."""
        self.stats.posts += 1
        n = len(payload["readings"])
        if self.dry_run:
            text = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                              indent=2 if self.pretty else None)
            print(text, file=self.out, flush=True)
            self.stats.ok += 1
            return "ok"
        try:
            status, body = self.sender(self.url, self.token, payload)
        except TransportError as e:
            self.stats.errors += 1
            self.log(f"seq={payload['seq']} n={n} -> server bilan aloqa yo'q ({e}); keyinroq qayta yuboriladi")
            return "retry"
        shown = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)[:300]
        self.log(f"seq={payload['seq']} n={n} -> HTTP {status} {shown}")
        if 200 <= status < 300:
            self.stats.ok += 1
            if isinstance(body, dict):
                self.stats.accepted += int(body.get("accepted") or 0)
                self.stats.flagged += int(body.get("flagged") or 0)
                if body.get("duplicate_batch"):
                    self.stats.duplicates += 1
            return "ok"
        if status in (401, 403):
            raise AuthError(f"HTTP {status}: {shown}")
        if status == 404:
            raise ConfigError(f"HTTP 404: {self.url} topilmadi ({shown}).\n"
                              f"--api qiymatini tekshiring (masalan {DEFAULT_API}).")
        if status in (408, 429) or status >= 500:
            self.stats.errors += 1
            return "retry"
        self.stats.errors += 1
        self.stats.dropped += n
        self.log(f"paket rad etildi (HTTP {status}) va tashlandi")
        return "drop"

    def send_readings(self, readings: list[dict]) -> None:
        """Navbatga qo'shadi va hammasini ≤20 talik paketlarda yuboradi (firmware mantig'i)."""
        self.pending.extend(readings)
        if len(self.pending) > PENDING_MAX:
            drop = len(self.pending) - PENDING_MAX
            self.log(f"navbat to'ldi: eng eski {drop} ta o'lchov tashlandi")
            del self.pending[:drop]
        while self.pending:
            chunk = self.pending[:MAX_READINGS_PER_POST]
            seq = self.state.next_seq(self.device_id)
            payload = build_payload(self.device_id, seq, chunk, self._rssi(), self._battery(chunk))
            self.last_payload = payload
            res = self._post(payload)
            if res == "retry":
                break
            del self.pending[:len(chunk)]

    def run_cycle(self, readings: list[dict]) -> None:
        cycle = self.cycle
        self.cycle += 1
        if self.is_offline_cycle(cycle):
            self.pending.extend(readings)
            self.was_offline = True
            self.log(f"[offline] aloqa yo'q — {len(readings)} ta o'lchov buferga yozildi "
                     f"(buferda {len(self.pending)} ta)")
            return
        flushing = self.was_offline
        if flushing:
            self.log(f"[offline] aloqa tiklandi — buferdagi {len(self.pending)} ta o'lchov "
                     f"asl vaqt belgilari bilan kechikib yuboriladi")
        self.send_readings(readings)
        if flushing and self.last_payload is not None and not self.pending:
            self.was_offline = False
            self.log(f"[offline] ataylab takroriy paket (seq={self.last_payload['seq']}) — "
                     f"server duplicate_batch=true qaytarishi kerak")
            self._post(self.last_payload)

    def backfill(self, hours: float, step_min: float, now: datetime, batch: int, pause_s: float) -> None:
        """O'tgan `hours` soat uchun tarixiy ma'lumot (asl vaqt belgilari bilan)."""
        n = int(hours * 60 // step_min)
        start = now - timedelta(minutes=step_min * n)
        times = [start + timedelta(minutes=step_min * i) for i in range(n + 1)]
        self.log(f"backfill: {len(times)} ta o'lchov, {iso_utc(times[0])} … {iso_utc(times[-1])}, "
                 f"har {step_min:g} daqiqada")
        readings = [self.model.next_reading(t) for t in times]
        for i in range(0, len(readings), batch):
            chunk = readings[i:i + batch]
            seq = self.state.next_seq(self.device_id)
            payload = build_payload(self.device_id, seq, chunk, self._rssi(), self._battery(chunk))
            self.last_payload = payload
            if self._post(payload) == "retry":
                self.pending.extend(chunk)
            if pause_s > 0 and not self.dry_run:
                time.sleep(pause_s)


# --------------------------------------------------------------------------- CLI
def load_devices(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("devices", [data])
    devices = []
    for i, d in enumerate(data):
        if not isinstance(d, dict) or not d.get("device_id") or not d.get("token"):
            raise ValueError(f"{path}: {i}-element'da device_id va token bo'lishi kerak")
        devices.append(d)
    if not devices:
        raise ValueError(f"{path}: qurilmalar ro'yxati bo'sh")
    return devices


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="sim.py",
        description="Smart Agro AI virtual IoT sensor simulyatori (ESP32 bilan bir xil API).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--api", default=os.environ.get("SIM_API", DEFAULT_API),
                   help="API bazaviy URL (…/api/v1)")
    p.add_argument("--device-id", help="qurilma ID (Mini App bergan)")
    p.add_argument("--token", default=os.environ.get("SIM_TOKEN"), help="qurilma tokeni (sa_…)")
    p.add_argument("--devices-file", type=Path,
                   help=f"JSON ro'yxat [{{device_id, token}}]; default: {DEFAULT_DEVICES_FILE.name} (agar bor bo'lsa)")
    p.add_argument("--scenario", choices=SCENARIOS, default="normal")
    p.add_argument("--interval", type=float, default=15.0, help="POST'lar orasidagi real soniya")
    p.add_argument("--count", type=int, default=None, help="jonli POST'lar soni (default: cheksiz; 0 = faqat backfill)")
    p.add_argument("--readings-per-post", type=int, default=1, help="har POST'dagi o'lchovlar (interval ichida teng taqsimlanadi)")
    p.add_argument("--speed", type=float, default=None,
                   help="vaqtni siqish: 1 real soniyada necha simulyatsiya daqiqasi (model uchun; ts baribir real UTC 'hozir')")
    p.add_argument("--backfill-hours", type=float, default=None,
                   help="avval o'tgan N soatlik tarixiy ma'lumotni yuborish (asl o'tmish vaqt belgilari bilan)")
    p.add_argument("--backfill-step-min", type=float, default=10.0, help="backfill o'lchovlari oralig'i (daqiqa)")
    p.add_argument("--offline-batches", type=int, default=4, help="offline ssenariyda nechta sikl aloqasiz o'tadi")
    p.add_argument("--seed", type=int, default=None, help="takrorlanuvchi natija uchun random seed")
    p.add_argument("--lat", type=float, default=40.12, help="dala kengligi (quyosh modeli uchun)")
    p.add_argument("--lon", type=float, default=67.84, help="dala uzunligi (quyosh modeli uchun)")
    p.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE, help="seq holati fayli")
    p.add_argument("--dry-run", action="store_true", help="yubormasdan payload'larni chiqarish (seq saqlanmaydi)")
    p.add_argument("--pretty", action="store_true", help="--dry-run payload'larini chiroyli formatlash")
    args = p.parse_args(argv)
    if args.interval < 0:
        p.error("--interval manfiy bo'lishi mumkin emas")
    if args.count is not None and args.count < 0:
        p.error("--count manfiy bo'lishi mumkin emas")
    if args.readings_per_post < 1 or args.readings_per_post > MAX_READINGS_PER_POST:
        p.error(f"--readings-per-post 1..{MAX_READINGS_PER_POST} oralig'ida bo'lishi kerak")
    if args.speed is not None and args.speed <= 0:
        p.error("--speed musbat bo'lishi kerak")
    if args.backfill_step_min <= 0:
        p.error("--backfill-step-min musbat bo'lishi kerak")
    return args


TOKEN_HOWTO = (
    "  • Mini App → Qurilmalar → \"Qurilma qo'shish\" orqali yangi qurilma yarating va tokenni nusxalang;\n"
    "  • yoki demo seed yozgan simulator/devices.json faylini tekshiring;\n"
    "  • so'ng: python3 simulator/sim.py --device-id <ID> --token <TOKEN> …"
)
AUTH_HELP = "Token yoki device_id noto'g'ri (yoki qurilma o'chirilgan).\n" + TOKEN_HOWTO


def resolve_devices(args: argparse.Namespace) -> list[dict]:
    if args.device_id:
        if not args.token:
            if args.dry_run:
                return [{"device_id": args.device_id, "token": "dry-run"}]
            raise ConfigError("--device-id bilan birga --token (yoki SIM_TOKEN env) ham kerak.\n" + TOKEN_HOWTO)
        return [{"device_id": args.device_id, "token": args.token}]
    path = args.devices_file or (DEFAULT_DEVICES_FILE if DEFAULT_DEVICES_FILE.exists() else None)
    if path is None:
        if args.dry_run:
            return [{"device_id": "esp32-sim-001", "token": "dry-run"}]
        raise ConfigError(
            "Qurilma ma'lumotlari berilmagan: --device-id + --token yoki --devices-file kerak "
            f"({DEFAULT_DEVICES_FILE} topilmadi).\n" + TOKEN_HOWTO)
    try:
        return load_devices(path)
    except FileNotFoundError:
        raise ConfigError(f"Fayl topilmadi: {path}")
    except (ValueError, json.JSONDecodeError) as e:
        raise ConfigError(f"Qurilmalar fayli noto'g'ri: {e}")


def run(args: argparse.Namespace, sender: Optional[Sender] = None, out=None,
        sleep: Callable[[float], None] = time.sleep) -> int:
    out = out or sys.stdout
    devices_cfg = resolve_devices(args)
    state = StateStore(args.state_file, persist=not args.dry_run)
    devices = []
    for i, d in enumerate(devices_cfg):
        seed = None if args.seed is None else args.seed + i * 1000
        scenario = d.get("scenario") or args.scenario
        if scenario not in SCENARIOS:
            raise ConfigError(f"{d['device_id']}: noma'lum ssenariy {scenario}")
        devices.append(VirtualDevice(
            d["device_id"], d["token"], scenario, args.api, state, sender=sender,
            dry_run=args.dry_run, seed=seed, lat=float(d.get("lat", args.lat)),
            lon=float(d.get("lon", args.lon)), offline_batches=args.offline_batches,
            out=out, pretty=args.pretty))

    mode = "DRY-RUN (yuborilmaydi)" if args.dry_run else args.api
    print(f"Smart Agro AI simulyator: {len(devices)} ta qurilma, ssenariy={args.scenario}, "
          f"interval={args.interval:g}s, count={'∞' if args.count is None else args.count}, "
          f"speed={args.speed if args.speed else 'real vaqt'} -> {mode}", file=out, flush=True)

    if args.backfill_hours:
        now = utc_now()
        for dev in devices:
            dev.backfill(args.backfill_hours, args.backfill_step_min, now,
                         batch=MAX_READINGS_PER_POST, pause_s=0.2)

    start = utc_now()

    def model_time(ts: datetime) -> datetime:
        if not args.speed:
            return ts
        return start + (ts - start) * (args.speed * 60.0)

    cycle = 0
    while args.count is None or cycle < args.count:
        t_now = utc_now()
        for dev in devices:
            readings = dev.make_readings(t_now, args.readings_per_post, args.interval, model_time)
            dev.run_cycle(readings)
        cycle += 1
        if args.count is None or cycle < args.count:
            sleep(args.interval)

    total = Stats()
    for dev in devices:
        for k in vars(total):
            setattr(total, k, getattr(total, k) + getattr(dev.stats, k))
    print(f"Yakun: POST={total.posts}, OK={total.ok}, accepted={total.accepted}, "
          f"duplicate_batch={total.duplicates}, flagged={total.flagged}, xatolar={total.errors}",
          file=out, flush=True)
    unsent = sum(len(d.pending) for d in devices)
    if unsent:
        print(f"OGOHLANTIRISH: {unsent} ta o'lchov yuborilmay qoldi (server bilan aloqa yo'q edi)",
              file=out, flush=True)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except AuthError as e:
        print(f"\nXATO (avtorizatsiya): {e}\n{AUTH_HELP}", file=sys.stderr)
        return 2
    except ConfigError as e:
        print(f"\nXATO (sozlama): {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\nTo'xtatildi (Ctrl+C).", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
