"""Sensor ma'lumotlari sifat nazorati (IOT-7): diapazon, qotib qolish, sakrash, manbalararo tekshiruv."""
from dataclasses import dataclass
from datetime import datetime

# IoT payload kaliti -> (ichki metrika, birlik)
PAYLOAD_METRICS = {
    "soil_moisture_vwc": ("soil_moisture", "%"),
    "soil_temp_c": ("soil_temp", "°C"),
    "air_temp_c": ("air_temp", "°C"),
    "air_rh": ("air_humidity", "%"),
    "light_lux": ("light", "lx"),
    "rain": ("rain", "bool"),
}

METRIC_LABEL_UZ = {
    "soil_moisture": "Tuproq namligi",
    "soil_temp": "Tuproq harorati",
    "air_temp": "Havo harorati",
    "air_humidity": "Havo namligi",
    "light": "Yorug'lik",
    "rain": "Yomg'ir sensori",
}

# Fizik jihatdan mumkin bo'lgan diapazonlar
PHYSICAL_RANGE = {
    "soil_moisture": (0.0, 60.0),
    "soil_temp": (-30.0, 60.0),
    "air_temp": (-40.0, 55.0),
    "air_humidity": (0.0, 100.0),
    "light": (0.0, 150000.0),
    "rain": (0.0, 1.0),
}

# 15 daqiqa ichida ruxsat etilgan maksimal o'zgarish (undan katta — "sakrash").
# Tuproq namligining keskin OSHISHI sug'orish/yomg'irda normal, shuning uchun faqat keskin tushish tekshiriladi.
MAX_STEP_15MIN = {"air_temp": 10.0, "soil_temp": 5.0, "air_humidity": 40.0, "soil_moisture_drop": 15.0}
STUCK_COUNT = 12  # ketma-ket bir xil qiymatlar soni
STUCK_METRICS = {"soil_moisture", "soil_temp", "air_temp", "air_humidity"}
CROSS_CHECK_AIR_TEMP_DELTA = 10.0


@dataclass
class QCResult:
    flag: str  # ok | suspect | bad
    reason: str | None = None


def check_reading(
    metric: str,
    value: float,
    ts: datetime,
    history: list[tuple[datetime, float]],
    model_air_temp: float | None = None,
) -> QCResult:
    """history — shu qurilma va metrika bo'yicha oldingi qiymatlar (eskidan yangiga)."""
    lo, hi = PHYSICAL_RANGE.get(metric, (float("-inf"), float("inf")))
    if not (lo <= value <= hi):
        return QCResult("bad", f"fizik diapazondan tashqarida ({lo}…{hi})")

    if metric in STUCK_METRICS and len(history) >= STUCK_COUNT - 1:
        last = [v for _, v in history[-(STUCK_COUNT - 1):]]
        if all(v == value for v in last):
            return QCResult("suspect", f"qiymat {STUCK_COUNT} marta ketma-ket o'zgarmagan (sensor qotib qolgan bo'lishi mumkin)")

    if history:
        prev_ts, prev_v = history[-1]
        minutes = max((ts - prev_ts).total_seconds() / 60, 1.0)
        if minutes <= 30:
            scale = minutes / 15
            if metric == "soil_moisture":
                if prev_v - value > MAX_STEP_15MIN["soil_moisture_drop"] * max(scale, 1):
                    return QCResult("suspect", "tuproq namligi keskin tushdi")
            elif metric in MAX_STEP_15MIN and abs(value - prev_v) > MAX_STEP_15MIN[metric] * max(scale, 1):
                return QCResult("suspect", "keskin sakrash")

    if metric == "air_temp" and model_air_temp is not None:
        if abs(value - model_air_temp) > CROSS_CHECK_AIR_TEMP_DELTA:
            return QCResult("suspect", f"ob-havo modelidan {abs(value - model_air_temp):.1f}°C farq qiladi")

    return QCResult("ok")


def device_offline(last_seen: datetime | None, now: datetime, expected_interval_min: int, factor: float) -> bool:
    if last_seen is None:
        return False
    return (now - last_seen).total_seconds() > expected_interval_min * 60 * factor
