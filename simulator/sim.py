#!/usr/bin/env python3
"""Smart Agro AI — virtual IoT sensor simulator.

Real qurilma bilan bir xil API'dan foydalanadi. Ikki format:

    --format telemetry (default)  POST {api}/iot/telemetry   — ESP32 + SIM7600G-H sxemasi
        (sig'imli namlik GPIO34, DS18B20 GPIO4, BME280 + BH1750 I2C, yomg'ir o'lchagich GPIO27)
    --format readings             POST {api}/iot/readings    — eski Wi-Fi firmware formati

Ikkalasida ham: Authorization: Bearer <device_token>.
Faqat Python standart kutubxonasi (3.10+), tashqi bog'liqliklar yo'q.

Misollar:
    python3 simulator/sim.py --scenario drought
    python3 simulator/sim.py --device-id esp32-7f3a --token sa_xxx --scenario frost
    python3 simulator/sim.py --dry-run --count 3 --interval 0 --pretty
    python3 simulator/sim.py --scenario normal --backfill-hours 24 --count 0
    python3 simulator/sim.py --format readings --readings-per-post 4
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
# 8088 — lokal nginx (8000-port bu mashinada boshqa loyihaga tegishli)
DEFAULT_API = "http://localhost:8088/api/v1"
FORMATS = ("telemetry", "readings")
DEFAULT_FORMAT = "telemetry"
MAX_READINGS_PER_POST = 20          # firmware bilan bir xil
PENDING_MAX = 5000                  # qayta yuborish navbati limiti (readings)

# ---- telemetry formati (firmware/esp32-sim7600 bilan bir xil)
TELEMETRY_UNITS = {                 # kontrakt: docs/API_CONTRACT_V2.md "Datchik telemetriyasi"
    "soil_moisture": "%",           # sig'imli sensor (GPIO34) -> taxminiy VWC %
    "soil_temperature": "C",        # DS18B20 (GPIO4)
    "air_temperature": "C",         # BME280
    "air_humidity": "%",            # BME280
    "air_pressure": "hPa",          # BME280 (mutlaq / stansiya bosimi)
    "light_intensity": "lux",       # BH1750
    "rainfall": "mm",               # cho'michli yomg'ir o'lchagich (GPIO27), yuborish oralig'idagi yig'indi
}
TELEMETRY_KEYS = tuple(TELEMETRY_UNITS)
TELEMETRY_QUEUE_MAX = 96            # firmware QUEUE_MAX_PACKETS bilan bir xil (5 daqiqada ~8 soat)
CSQ_MAX = 31                        # AT+CSQ: 0..31 (99 = noma'lum — yuborilmaydi)
RAIN_MM_PER_TIP = 0.2               # 1 ta "tip" = 0.2 mm (o'lchagich pasportiga qarab kalibrlanadi)
HEAVY_RAIN_MM_H = 30.0              # heavy_rain ssenariysidagi yomg'ir jadalligi (to'liq kuchda)
DEFAULT_ELEVATION_M = 380.0         # Jizzax atrofi; bosim balandlikka qarab hisoblanadi
BH1750_MAX_LUX = 121557             # MTreg=31 da BH1750 to'yinish chegarasi (firmware shunday sozlaydi)
DS18B20_STEP_C = 0.0625             # 12-bit o'lchash qadami
FAULT_MISSING_METRIC = "soil_temperature"   # sensor_fault: DS18B20 uzilib qoladi

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
    inject_faults: bool = True                       # sensor_fault: qotish + 85 °C sakrashlar (readings)
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

        if self.inject_faults and self.scenario == "sensor_fault" and self.step >= FAULT_START_STEP:
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


# --------------------------------------------------------------------------- telemetry model
def sea_level_pressure_normal(t: datetime) -> float:
    """O'rtacha dengiz sathi bosimi, hPa: qishda Sibir antisikloni (~1024), yozda termik depressiya (~1006)."""
    doy = t.timetuple().tm_yday
    c = math.cos(2 * math.pi * (doy - 200) / 365.0)   # +1 iyul, -1 yanvar
    return 1015.0 - 9.0 * c


def station_pressure_hpa(msl_hpa: float, elevation_m: float) -> float:
    """Barometrik formula (ISA). BME280 mutlaq (stansiya) bosimni o'lchaydi, dengiz sathiga keltirmaydi."""
    return msl_hpa * (1.0 - 2.25577e-5 * elevation_m) ** 5.25588


def csq_from_rssi(rssi_dbm: float) -> int:
    """3GPP TS 27.007: CSQ = (RSSI + 113) / 2, 0..31."""
    return int(max(0, min(CSQ_MAX, round((rssi_dbm + 113.0) / 2.0))))


@dataclass
class TelemetryModel:
    """ESP32 + SIM7600G-H sxemasidagi datchiklar: FieldModel ustiga BME280 bosimi, BH1750 to'yinishi,
    DS18B20 kvantlash, cho'michli yomg'ir o'lchagich va telemetriya uchun sensor nosozliklari."""

    scenario: str = "normal"
    seed: Optional[int] = None
    lat: float = 40.12
    lon: float = 67.84
    elevation_m: float = DEFAULT_ELEVATION_M
    mm_per_tip: float = RAIN_MM_PER_TIP
    first_interval_s: float = 300.0       # birinchi paket qamraydigan (model) vaqt — yomg'ir yig'indisi uchun
    base: FieldModel = field(init=False)
    rng: random.Random = field(init=False)
    synoptic: float = field(init=False, default=0.0)     # sinoptik bosim og'ishi, hPa
    bucket_mm: float = field(init=False, default=0.0)    # cho'michda yig'ilgan, hali ag'darilmagan suv
    total_tips: int = field(init=False, default=0)
    step: int = field(init=False, default=0)
    last_model_time: Optional[datetime] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.mm_per_tip <= 0:
            raise ValueError("mm_per_tip musbat bo'lishi kerak")
        self.base = FieldModel(scenario=self.scenario, seed=self.seed, lat=self.lat, lon=self.lon,
                               inject_faults=False)
        self.rng = random.Random(None if self.seed is None else self.seed + 104729)
        self.synoptic = self.rng.uniform(-3.0, 3.0)

    def rain_rate_mm_h(self, s: float) -> float:
        if self.scenario != "heavy_rain":
            return 0.0
        gust = max(0.3, 1.0 + self.rng.gauss(0, 0.3))
        return HEAVY_RAIN_MM_H * (0.4 + 0.6 * s) * gust

    def pressure_hpa(self, mt: datetime, dt_h: float, s: float) -> float:
        # Ornstein–Uhlenbeck: tau 48 soat, statsionar sigma ~5 hPa
        tau, sigma = 48.0, 5.0
        if dt_h > 0:
            k = min(1.0, dt_h / tau)
            self.synoptic += -self.synoptic * k + sigma * math.sqrt(2.0 * k) * self.rng.gauss(0, 1)
            self.synoptic = max(-12.0, min(12.0, self.synoptic))
        msl = sea_level_pressure_normal(mt) + self.synoptic
        if self.scenario == "heavy_rain":
            msl -= 12.0 * s                     # siklon
        elif self.scenario == "frost":
            msl += 10.0 * s                     # antisiklon, ochiq osmon
        elif self.scenario == "drought":
            msl -= 4.0 * s                      # termik depressiya
        msl += 0.8 * math.cos(2 * math.pi * (solar_hour(mt, self.lon) - 10.0) / 12.0)   # yarim sutkalik to'lqin
        return station_pressure_hpa(msl, self.elevation_m) + self.rng.gauss(0, 0.05)

    def next_values(self, ts: datetime, model_time: Optional[datetime] = None) -> tuple[dict, list[str]]:
        """({o'lchov_kaliti: qiymat}, sensor_errors). Ishlamayotgan datchik kaliti umuman qaytarilmaydi."""
        mt = model_time or ts
        if self.last_model_time is None:
            dt_h = max(0.0, self.first_interval_s) / 3600.0
        else:
            dt_h = max(0.0, (mt - self.last_model_time).total_seconds() / 3600.0)
        self.last_model_time = mt
        s = self.base.intensity()
        r = self.base.next_reading(ts, mt)

        # cho'michli o'lchagich: suv yig'iladi, har mm_per_tip da bitta impuls (qoldiq keyingi oraliqqa o'tadi)
        self.bucket_mm += self.rain_rate_mm_h(s) * dt_h
        tips = int((self.bucket_mm + 1e-9) / self.mm_per_tip)
        self.bucket_mm = max(0.0, self.bucket_mm - tips * self.mm_per_tip)
        self.total_tips += tips

        soil_t = round(r["soil_temp_c"] / DS18B20_STEP_C) * DS18B20_STEP_C
        values = {
            "soil_moisture": r["soil_moisture_vwc"],
            "soil_temperature": round(soil_t, 2),
            "air_temperature": round(r["air_temp_c"], 2),
            "air_humidity": r["air_rh"],
            "air_pressure": round(self.pressure_hpa(mt, dt_h, s), 1),
            "light_intensity": int(min(BH1750_MAX_LUX, r["light_lux"])),
            "rainfall": round(tips * self.mm_per_tip, 3),
        }
        errors: list[str] = []
        if self.scenario == "sensor_fault":
            if self.step >= FAULT_START_STEP:          # DS18B20 uzildi (-127 °C) -> qiymat yuborilmaydi
                values.pop(FAULT_MISSING_METRIC)
                errors.append(FAULT_MISSING_METRIC)
            if self.step == FAULT_SPIKE_FIRST:         # bitta diapazondan tashqari sakrash
                values["air_temperature"] = FAULT_SPIKE_VALUE
        self.step += 1
        return values, errors


def build_telemetry_payload(device_id: str, ts: datetime, values: dict, signal_quality: Optional[int],
                            sensor_errors: list[str], simulated: bool = True) -> dict:
    """Kontrakt shakli: {device_id, timestamp, measurements{k: {value, unit}}, status{signal_quality, sensor_errors}}.

    status.simulated=true — backend bu ma'lumotni "simulator" manbasi deb belgilaydi (real qurilma yubormaydi).
    signal_quality=None (modem CSQ=99, noma'lum) bo'lsa kalit yuborilmaydi."""
    unknown = (set(values) | set(sensor_errors)) - set(TELEMETRY_KEYS)
    if unknown:
        raise ValueError(f"noma'lum o'lchov kaliti: {sorted(unknown)}")
    measurements = {k: {"value": values[k], "unit": TELEMETRY_UNITS[k]} for k in TELEMETRY_KEYS if k in values}
    status: dict = {}
    if signal_quality is not None:
        status["signal_quality"] = int(signal_quality)
    status["sensor_errors"] = list(sensor_errors)
    if simulated:
        status["simulated"] = True
    return {
        "device_id": device_id,
        "timestamp": iso_utc(ts),
        "measurements": measurements,
        "status": status,
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
                 online_batches: int = 2, out=None, pretty: bool = False, fmt: str = DEFAULT_FORMAT,
                 elevation_m: float = DEFAULT_ELEVATION_M, mm_per_tip: float = RAIN_MM_PER_TIP,
                 interval_s: float = 300.0):
        if fmt not in FORMATS:
            raise ValueError(f"noma'lum format: {fmt}")
        self.device_id = device_id
        self.token = token
        self.scenario = scenario
        self.fmt = fmt
        self.url = api.rstrip("/") + ("/iot/telemetry" if fmt == "telemetry" else "/iot/readings")
        self.state = state
        self.sender = sender or (lambda url, tok, p: http_post_json(url, tok, p))
        self.dry_run = dry_run
        self.rng = random.Random(None if seed is None else seed + 7919)
        self.model = FieldModel(scenario=scenario, seed=seed, lat=lat, lon=lon)
        self.tmodel: Optional[TelemetryModel] = None
        if fmt == "telemetry":
            self.tmodel = TelemetryModel(scenario=scenario, seed=seed, lat=lat, lon=lon,
                                         elevation_m=elevation_m, mm_per_tip=mm_per_tip,
                                         first_interval_s=interval_s)
        self.offline_batches = max(1, offline_batches)
        self.online_batches = max(1, online_batches)
        self.pending: list[dict] = []        # readings: o'lchovlar; telemetry: paketlar
        self.cycle = 0
        self.was_offline = False
        self.last_payload: Optional[dict] = None
        self.last_ts: Optional[datetime] = None
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

    def _csq(self, offline: bool = False) -> int:
        rssi = self._rssi()
        if offline:                          # qamrov yo'q: signal juda past
            return self.rng.randint(0, 5)
        return csq_from_rssi(rssi)

    def _battery(self, readings: list[dict]) -> float:
        lux = readings[-1].get("light_lux", 0) if readings else 0
        return 3.72 + 0.35 * min(1.0, lux / 100000.0) + self.rng.gauss(0, 0.01)

    def is_offline_cycle(self, cycle: int) -> bool:
        if self.scenario != "offline":
            return False
        period = self.online_batches + self.offline_batches
        return (cycle % period) >= self.online_batches

    @staticmethod
    def _describe(payload: dict) -> tuple[str, int]:
        """(log uchun yorliq, paketdagi birliklar soni)."""
        if "readings" in payload:
            n = len(payload["readings"])
            return f"seq={payload['seq']} n={n}", n
        return f"ts={payload['timestamp']} n={len(payload['measurements'])}", 1

    # ---- o'lchovlar (readings)
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

    # ---- telemetriya paketi
    def make_packet(self, t: datetime, model_time: Callable[[datetime], datetime] = lambda t: t,
                    offline: bool = False) -> dict:
        """Bitta telemetriya paketi. timestamp har qurilma uchun qat'iy o'sadi (server (device_id, timestamp)
        bo'yicha dublikatni aniqlaydi, shuning uchun bir soniyada ikki paket bo'lmasligi kerak)."""
        if self.tmodel is None:
            raise RuntimeError("make_packet faqat --format telemetry uchun")
        ts = t.astimezone(timezone.utc).replace(microsecond=0)
        if self.last_ts is not None and ts <= self.last_ts:
            ts = self.last_ts + timedelta(seconds=1)
        self.last_ts = ts
        values, errors = self.tmodel.next_values(ts, model_time(ts))
        return build_telemetry_payload(self.device_id, ts, values, self._csq(offline), errors)

    # ---- yuborish
    def _post(self, payload: dict) -> str:
        """'ok' | 'retry' | 'drop'. AuthError/ConfigError yuqoriga uzatiladi."""
        self.stats.posts += 1
        label, n = self._describe(payload)
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
            self.log(f"{label} -> server bilan aloqa yo'q ({e}); keyinroq qayta yuboriladi")
            return "retry"
        shown = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)[:300]
        self.log(f"{label} -> HTTP {status} {shown}")
        if 200 <= status < 300:
            self.stats.ok += 1
            if isinstance(body, dict):
                self.stats.accepted += int(body.get("accepted") or 0)
                self.stats.flagged += int(body.get("flagged") or 0)
                if body.get("duplicate_batch") or body.get("duplicate") is True:
                    self.stats.duplicates += 1
            return "ok"
        if status in (401, 403):
            raise AuthError(f"HTTP {status}: {shown}")
        if status in (404, 405):
            raise ConfigError(f"HTTP {status}: {self.url} topilmadi ({shown}).\n"
                              f"--api qiymatini tekshiring (masalan {DEFAULT_API}); "
                              f"backend {'/iot/telemetry' if self.fmt == 'telemetry' else '/iot/readings'} "
                              f"endpointini qo'llab-quvvatlashi kerak (yoki --format ni almashtiring).")
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

    def enqueue_packets(self, packets: list[dict]) -> None:
        """Cheklangan navbat (firmware kabi): to'lsa eng eski paketlar tashlanadi."""
        self.pending.extend(packets)
        if len(self.pending) > TELEMETRY_QUEUE_MAX:
            drop = len(self.pending) - TELEMETRY_QUEUE_MAX
            self.log(f"navbat to'ldi ({TELEMETRY_QUEUE_MAX}): eng eski {drop} ta paket tashlandi")
            self.stats.dropped += drop
            del self.pending[:drop]

    def send_packets(self, packets: list[dict]) -> None:
        """Navbatga qo'shadi va eskisidan boshlab bittadan yuboradi; vaqtinchalik xatoda to'xtaydi."""
        self.enqueue_packets(packets)
        while self.pending:
            pkt = self.pending[0]
            self.last_payload = pkt
            if self._post(pkt) == "retry":
                break
            self.pending.pop(0)

    def _deliver(self, items: list[dict]) -> None:
        if self.fmt == "telemetry":
            self.send_packets(items)
        else:
            self.send_readings(items)

    def _buffer_offline(self, items: list[dict]) -> None:
        if self.fmt == "telemetry":
            self.enqueue_packets(items)
            what = "paket"
        else:
            self.pending.extend(items)
            what = "o'lchov"
        self.was_offline = True
        self.log(f"[offline] aloqa yo'q — {len(items)} ta {what} buferga yozildi "
                 f"(buferda {len(self.pending)} ta)")

    def run_cycle(self, items: list[dict]) -> None:
        """Bitta yuborish sikli: readings ro'yxati yoki telemetriya paketlari (format bo'yicha)."""
        cycle = self.cycle
        self.cycle += 1
        if self.is_offline_cycle(cycle):
            self._buffer_offline(items)
            return
        flushing = self.was_offline
        if flushing:
            what = "paket" if self.fmt == "telemetry" else "o'lchov"
            self.log(f"[offline] aloqa tiklandi — buferdagi {len(self.pending)} ta {what} "
                     f"asl vaqt belgilari bilan kechikib yuboriladi")
        self._deliver(items)
        if flushing and self.last_payload is not None and not self.pending:
            self.was_offline = False
            if self.fmt == "telemetry":
                self.log(f"[offline] ataylab takroriy paket (timestamp={self.last_payload['timestamp']}) — "
                         f"server duplicate=true qaytarishi kerak")
            else:
                self.log(f"[offline] ataylab takroriy paket (seq={self.last_payload['seq']}) — "
                         f"server duplicate_batch=true qaytarishi kerak")
            self._post(self.last_payload)

    def telemetry_cycle(self, t: datetime,
                        model_time: Callable[[datetime], datetime] = lambda t: t) -> dict:
        """Telemetriya: paket yasaydi (offline siklda signal past) va run_cycle orqali yuboradi."""
        packet = self.make_packet(t, model_time, offline=self.is_offline_cycle(self.cycle))
        self.run_cycle([packet])
        return packet

    def backfill(self, hours: float, step_min: float, now: datetime, batch: int, pause_s: float) -> None:
        """O'tgan `hours` soat uchun tarixiy ma'lumot (asl vaqt belgilari bilan)."""
        n = int(hours * 60 // step_min)
        start = now - timedelta(minutes=step_min * n)
        times = [start + timedelta(minutes=step_min * i) for i in range(n + 1)]
        unit = "paket" if self.fmt == "telemetry" else "o'lchov"
        self.log(f"backfill: {len(times)} ta {unit}, {iso_utc(times[0])} … {iso_utc(times[-1])}, "
                 f"har {step_min:g} daqiqada")
        if self.fmt == "telemetry":
            assert self.tmodel is not None
            if self.tmodel.last_model_time is None:
                self.tmodel.first_interval_s = step_min * 60.0
            for t in times:
                pkt = self.make_packet(t)
                self.last_payload = pkt
                if self._post(pkt) == "retry":
                    self.enqueue_packets([pkt])
                if pause_s > 0 and not self.dry_run:
                    time.sleep(pause_s)
            return
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
        description="Smart Agro AI virtual IoT sensor simulyatori (ESP32 + SIM7600G-H qurilmasi bilan bir xil API).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--api", default=os.environ.get("SIM_API", DEFAULT_API),
                   help="API bazaviy URL (…/api/v1)")
    p.add_argument("--format", choices=FORMATS, default=DEFAULT_FORMAT,
                   help="telemetry = POST {api}/iot/telemetry (ESP32 + SIM7600G-H sxemasi); "
                        "readings = eski POST {api}/iot/readings")
    p.add_argument("--device-id", help="qurilma ID (Mini App bergan)")
    p.add_argument("--token", default=os.environ.get("SIM_TOKEN"), help="qurilma tokeni (sa_…)")
    p.add_argument("--devices-file", type=Path,
                   help=f"JSON ro'yxat [{{device_id, token}}]; default: {DEFAULT_DEVICES_FILE.name} (agar bor bo'lsa)")
    p.add_argument("--scenario", choices=SCENARIOS, default="normal")
    p.add_argument("--interval", type=float, default=15.0, help="POST'lar orasidagi real soniya")
    p.add_argument("--count", type=int, default=None, help="jonli POST'lar soni (default: cheksiz; 0 = faqat backfill)")
    p.add_argument("--readings-per-post", type=int, default=1,
                   help="faqat --format readings: har POST'dagi o'lchovlar (interval ichida teng taqsimlanadi)")
    p.add_argument("--speed", type=float, default=None,
                   help="vaqtni siqish: 1 real soniyada necha simulyatsiya daqiqasi (model uchun; ts baribir real UTC 'hozir')")
    p.add_argument("--backfill-hours", type=float, default=None,
                   help="avval o'tgan N soatlik tarixiy ma'lumotni yuborish (asl o'tmish vaqt belgilari bilan)")
    p.add_argument("--backfill-step-min", type=float, default=10.0, help="backfill o'lchovlari oralig'i (daqiqa)")
    p.add_argument("--offline-batches", type=int, default=4, help="offline ssenariyda nechta sikl aloqasiz o'tadi")
    p.add_argument("--seed", type=int, default=None, help="takrorlanuvchi natija uchun random seed")
    p.add_argument("--lat", type=float, default=40.12, help="dala kengligi (quyosh modeli uchun)")
    p.add_argument("--lon", type=float, default=67.84, help="dala uzunligi (quyosh modeli uchun)")
    p.add_argument("--elevation", type=float, default=DEFAULT_ELEVATION_M,
                   help="dala balandligi, m (BME280 mutlaq bosimi: 0 m ≈ 1013 hPa, 1000 m ≈ 900 hPa)")
    p.add_argument("--mm-per-tip", type=float, default=RAIN_MM_PER_TIP,
                   help="yomg'ir o'lchagichning bitta impulsi necha mm (o'lchagich pasportidan)")
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
    if args.format == "telemetry" and args.readings_per_post != 1:
        p.error("--readings-per-post faqat --format readings bilan ishlaydi "
                "(telemetriyada har POST = bitta paket)")
    if not -100.0 <= args.elevation <= 3000.0:
        p.error("--elevation -100..3000 m oralig'ida bo'lishi kerak")
    if not 0.0 < args.mm_per_tip <= 5.0:
        p.error("--mm-per-tip 0..5 mm oralig'ida bo'lishi kerak")
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
    fmt = getattr(args, "format", DEFAULT_FORMAT)
    devices_cfg = resolve_devices(args)
    state = StateStore(args.state_file, persist=not args.dry_run)
    # birinchi telemetriya paketi qamraydigan model vaqti (yomg'ir yig'indisi uchun)
    interval_model_s = args.interval * (args.speed * 60.0 if args.speed else 1.0)
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
            out=out, pretty=args.pretty, fmt=fmt,
            elevation_m=float(d.get("elevation", getattr(args, "elevation", DEFAULT_ELEVATION_M))),
            mm_per_tip=getattr(args, "mm_per_tip", RAIN_MM_PER_TIP), interval_s=interval_model_s))

    mode = "DRY-RUN (yuborilmaydi)" if args.dry_run else devices[0].url
    print(f"Smart Agro AI simulyator: {len(devices)} ta qurilma, format={fmt}, ssenariy={args.scenario}, "
          f"interval={args.interval:g}s, count={'∞' if args.count is None else args.count}, "
          f"speed={args.speed if args.speed else 'real vaqt'} -> {mode}", file=out, flush=True)

    if args.backfill_hours:
        now = utc_now()
        for dev in devices:
            dev.backfill(args.backfill_hours, args.backfill_step_min, now,
                         batch=MAX_READINGS_PER_POST, pause_s=0.05 if fmt == "telemetry" else 0.2)

    start = utc_now()

    def model_time(ts: datetime) -> datetime:
        if not args.speed:
            return ts
        return start + (ts - start) * (args.speed * 60.0)

    cycle = 0
    while args.count is None or cycle < args.count:
        t_now = utc_now()
        for dev in devices:
            if fmt == "telemetry":
                dev.telemetry_cycle(t_now, model_time)
            else:
                readings = dev.make_readings(t_now, args.readings_per_post, args.interval, model_time)
                dev.run_cycle(readings)
        cycle += 1
        if args.count is None or cycle < args.count:
            sleep(args.interval)

    total = Stats()
    for dev in devices:
        for k in vars(total):
            setattr(total, k, getattr(total, k) + getattr(dev.stats, k))
    dup_label = "duplicate" if fmt == "telemetry" else "duplicate_batch"
    print(f"Yakun: POST={total.posts}, OK={total.ok}, accepted={total.accepted}, "
          f"{dup_label}={total.duplicates}, flagged={total.flagged}, xatolar={total.errors}",
          file=out, flush=True)
    unsent = sum(len(d.pending) for d in devices)
    if unsent:
        what = "paket" if fmt == "telemetry" else "o'lchov"
        print(f"OGOHLANTIRISH: {unsent} ta {what} yuborilmay qoldi (server bilan aloqa yo'q edi)",
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
