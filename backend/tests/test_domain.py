"""Agronomik yadro va xavfsizlik unit testlari (DB kerak emas)."""
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest

from app.agent.validator import unknown_numbers, validate_texts
from app.core.security import InitDataError, validate_init_data
from app.domain import alerts, knowledge
from app.domain.climate import climate_shift, slope_per_decade, yearly_aggregates
from app.domain.et0 import et0_penman_monteith
from app.domain.gdd import gdd_sum
from app.domain.geo import GeometryError, grid_key, validate_polygon_geojson
from app.domain.qc import check_reading
from app.domain.rotation import plan_rotation
from app.domain.water_balance import SoilWater, depletion_from_vwc, ks_factor, run_balance
from app.domain.yield_model import Scenario, calibration_factor, estimate_yield, water_yield_ratio


# ---------------- ET0 — FAO-56 18-misol (Bryussel, 6-iyul): ET0 ≈ 3.9 mm/kun
def test_et0_fao56_example_18():
    et0 = et0_penman_monteith(t_min=12.3, t_max=21.5, ea=1.409, rs=22.07, u2=2.078, lat_deg=50.8, doy=187, elevation_m=100)
    assert et0 == pytest.approx(3.9, abs=0.1)


def test_gdd():
    assert gdd_sum([(10, 20), (0, 4), (12, 30)], t_base=10) == pytest.approx(5 + 0 + 11)


# ---------------- Suv balansi
def test_taw_raw_and_ks():
    sw = SoilWater(theta_fc=0.25, theta_wp=0.12, root_depth_m=1.0, p=0.5)
    assert sw.taw_mm == pytest.approx(130)
    assert sw.raw_mm == pytest.approx(65)
    assert ks_factor(60, sw) == 1.0
    assert ks_factor(130, sw) == 0.0


def test_balance_depletes_and_rain_refills():
    sw = SoilWater(0.25, 0.12, 1.0, 0.5)
    days = [{"day": str(i), "etc": 5.0, "rain": 0.0} for i in range(10)]
    res = run_balance(days, sw, 0)
    assert res.depletion == pytest.approx(50)
    res2 = run_balance(days + [{"day": "x", "etc": 0.0, "rain": 50.0}], sw, 0)
    assert res2.depletion == pytest.approx(10)  # 50 mm yog'inning 80% i samarali


def test_depletion_from_sensor():
    sw = SoilWater(0.25, 0.12, 1.0, 0.5)
    assert depletion_from_vwc(25.0, sw) == pytest.approx(0)
    assert depletion_from_vwc(12.0, sw) == pytest.approx(130)


# ---------------- Geometriya
def test_polygon_validation():
    square = {"type": "Polygon", "coordinates": [[[67.0, 40.0], [67.001, 40.0], [67.001, 40.001], [67.0, 40.001], [67.0, 40.0]]]}
    assert validate_polygon_geojson(square).is_valid
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    with pytest.raises(GeometryError, match="kesib"):
        validate_polygon_geojson(bowtie)
    with pytest.raises(GeometryError):
        validate_polygon_geojson({"type": "Polygon", "coordinates": [[[0, 0], [0, 0], [1, 1]]]})


def test_unclosed_ring_is_closed():
    quad = {"type": "Polygon", "coordinates": [[[67.0, 40.0], [67.001, 40.0], [67.001, 40.001], [67.0, 40.001]]]}
    assert validate_polygon_geojson(quad).is_valid


def test_grid_key_same_cell():
    assert grid_key(40.12, 67.84) == grid_key(40.2, 67.9)
    assert grid_key(40.12, 67.84) != grid_key(41.0, 67.84)


# ---------------- Sifat nazorati
NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def test_qc_range_stuck_spike_crosscheck():
    assert check_reading("air_temp", 85.0, NOW, []).flag == "bad"
    hist = [(NOW - timedelta(minutes=15 * i), 22.2) for i in range(11, 0, -1)]
    assert check_reading("soil_moisture", 22.2, NOW, hist).flag == "suspect"
    assert check_reading("air_temp", 30.0, NOW, [(NOW - timedelta(minutes=15), 15.0)]).flag == "suspect"
    assert check_reading("air_temp", 25.0, NOW, [], model_air_temp=10.0).flag == "suspect"
    assert check_reading("soil_moisture", 40.0, NOW, [(NOW - timedelta(minutes=15), 15.0)]).flag == "ok"  # sug'orish


# ---------------- Qoidalar
def _fact(v, source="model"):
    return {"value": v, "source": source}


def test_irrigation_rules():
    base = {"depletion_mm": _fact(70), "raw_mm": _fact(65), "taw_mm": _fact(130)}
    a = alerts.evaluate({**base, "fc_precip_48h": _fact(0.0, "forecast"), "fc_precip_prob_max_48h": _fact(5, "forecast")}, None, None)
    assert [x.type for x in a] == ["irrigation_needed"]
    a = alerts.evaluate({**base, "fc_precip_48h": _fact(15.0, "forecast"), "fc_precip_prob_max_48h": _fact(80, "forecast")}, None, None)
    assert [x.type for x in a] == ["irrigation_delay"]
    a = alerts.evaluate({**base, "depletion_mm": _fact(110)}, None, None)
    assert a[0].type == "soil_moisture_critical" and a[0].severity == "critical"


def test_frost_heat_rules():
    cotton = knowledge.crop("cotton")
    a = alerts.evaluate({"fc_tmin_72h": _fact(-2.0, "forecast")}, cotton, "ini")
    assert a[0].type == "frost_risk" and a[0].severity == "critical"
    a = alerts.evaluate({"fc_tmax_72h": _fact(39.0, "forecast"), "fc_hot_days_72h": _fact(3, "forecast")}, cotton, "mid")
    assert a[0].type == "heat_stress" and a[0].severity == "critical"
    assert alerts.evaluate({"fc_tmin_72h": _fact(-2.0, "forecast")}, cotton, "off") == []


# ---------------- Hosil va almashlab ekish
def test_fao33_water_yield():
    assert water_yield_ratio(1.0, 1.25) == 1.0
    assert water_yield_ratio(0.8, 1.25) == pytest.approx(0.75)


def test_calibration_shrinkage():
    k, n = calibration_factor([(6.0, 5.0)])
    assert n == 1 and 1.0 < k < 1.2


def test_estimate_yield_range_ordered():
    c = knowledge.crop("maize_grain")
    sc = [Scenario("dry", 700, 50), Scenario("normal", 600, 100), Scenario("wet", 520, 160)]
    est = estimate_yield(c, sc, water_available_m3_ha=4000, ece=None, farmer_pairs=[], farmer_yields=[])
    assert est.min_t_ha <= est.likely_t_ha <= est.max_t_ha
    assert est.confidence == "low"
    assert any("mintaqaviy" in a for a in est.assumptions)


def test_rotation_rules():
    cands = plan_rotation(["wheat_winter", "wheat_winter"], {}, None, None, None, {})
    by = {c.crop: c for c in cands}
    assert by["wheat_winter"].excluded  # 2 mavsum ketma-ket
    assert by["mung_bean"].score > by["maize_grain"].score  # dukkakli boshoqdoshlardan keyin
    salty = plan_rotation(["cotton"], {}, None, None, 6.0, {})
    assert {c.crop for c in salty if c.excluded} >= {"maize_grain", "mung_bean", "potato", "alfalfa"}


# ---------------- Iqlim siljishi
def test_climate_aggregates_and_trend():
    daily = {}
    for y in (2000, 2001):
        d = date(y, 1, 1)
        while d.year == y:
            daily[d] = {"T2M": 10 + (y - 2000), "T2M_MAX": 36 if d.month == 7 else 20, "T2M_MIN": -1 if d.month == 1 else 5,
                        "PRECTOTCORR": 1.0}
            d += timedelta(days=1)
    years = yearly_aggregates(daily)
    assert [y["year"] for y in years] == [2000, 2001]
    assert years[0]["hot_days"] == 31 and years[0]["frost_days"] == 31
    assert slope_per_decade([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 10
    assert "summary_uz" in climate_shift(years)


# ---------------- LLM raqam validatori
def test_validator_rejects_invented_numbers():
    payload = {"facts": {"soil_moisture": {"value": 14.2}}, "draft": "Taxminan 40 mm suv bering"}
    assert unknown_numbers("Namlik 14.2% — 40 mm sug'oring", {14.2, 40.0}) == []
    assert validate_texts(["Hosil 8.7 t/ga oshadi"], payload) == [8.7]
    assert validate_texts(["Namlik 14% atrofida, 2–3 kun ichida sug'oring"], payload) == []


# ---------------- Telegram initData
def _signed(bot_token: str, user: dict, auth_date: int) -> str:
    fields = {"auth_date": str(auth_date), "query_id": "AAH", "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_init_data_valid_forged_expired():
    token = "123456:TEST_TOKEN_abcdefghijklmnopqrstuvwxyz"
    user = {"id": 42, "first_name": "Ali"}
    good = _signed(token, user, int(time.time()))
    assert validate_init_data(good, token, 3600)["id"] == 42
    with pytest.raises(InitDataError):
        validate_init_data(good.replace("Ali", "Vali"), token, 3600)
    with pytest.raises(InitDataError):
        validate_init_data(_signed(token, user, int(time.time()) - 7200), token, 3600)
    with pytest.raises(InitDataError):
        validate_init_data(good, "999:other", 3600)
