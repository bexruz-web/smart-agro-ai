"""Iqlim siljishi (temp shift) va iqlim ssenariylari — NASA POWER kunlik tarixidan."""
import statistics
from collections import defaultdict
from datetime import date, timedelta

from app.domain import knowledge
from app.domain.et0 import extraterrestrial_radiation
from app.domain.water_balance import monthly_effective_rain
from app.domain.yield_model import Scenario, hargreaves_et0

HOT_DAY_C = 35.0
BASELINE = (1991, 2020)


def yearly_aggregates(daily: dict[date, dict]) -> list[dict]:
    """daily: {sana: {"T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"}} -> to'liq yillar agregatlari."""
    by_year: dict[int, list[dict]] = defaultdict(list)
    for d, v in daily.items():
        by_year[d.year].append(v)
    out = []
    for year in sorted(by_year):
        rows = by_year[year]
        t = [r["T2M"] for r in rows if r.get("T2M") is not None]
        p = [r["PRECTOTCORR"] for r in rows if r.get("PRECTOTCORR") is not None]
        tmax = [r["T2M_MAX"] for r in rows if r.get("T2M_MAX") is not None]
        tmin = [r["T2M_MIN"] for r in rows if r.get("T2M_MIN") is not None]
        if min(len(t), len(p), len(tmax), len(tmin)) < 360:
            continue  # to'liq bo'lmagan yil (masalan joriy yil) trendga kirmaydi
        out.append(
            {
                "year": year,
                "t_mean": round(statistics.fmean(t), 2),
                "precip_total": round(sum(p), 1),
                "hot_days": sum(1 for x in tmax if x > HOT_DAY_C),
                "frost_days": sum(1 for x in tmin if x < 0),
            }
        )
    return out


def slope_per_decade(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 5:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return round(10 * sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den, 2)


def climate_shift(years: list[dict]) -> dict:
    if not years:
        return {}
    xs = [y["year"] for y in years]
    trend = {
        f"{k}_per_decade": slope_per_decade(xs, [y[k] for y in years])
        for k in ("t_mean", "precip_total", "hot_days", "frost_days")
    }
    trend["precip_per_decade"] = trend.pop("precip_total_per_decade")
    base = [y for y in years if BASELINE[0] <= y["year"] <= BASELINE[1]]
    recent = years[-10:]
    rvb = {}
    if base and recent:
        b_t = statistics.fmean(y["t_mean"] for y in base)
        b_p = statistics.fmean(y["precip_total"] for y in base)
        b_h = statistics.fmean(y["hot_days"] for y in base)
        b_f = statistics.fmean(y["frost_days"] for y in base)
        r_t = statistics.fmean(y["t_mean"] for y in recent)
        r_p = statistics.fmean(y["precip_total"] for y in recent)
        r_h = statistics.fmean(y["hot_days"] for y in recent)
        r_f = statistics.fmean(y["frost_days"] for y in recent)
        rvb = {
            "period": f"{recent[0]['year']}–{recent[-1]['year']}",
            "t_mean_delta": round(r_t - b_t, 2),
            "precip_delta_pct": round(100 * (r_p - b_p) / b_p, 1) if b_p else None,
            "hot_days_delta": round(r_h - b_h, 1),
            "frost_days_delta": round(r_f - b_f, 1),
        }
    return {"trend": trend, "recent_vs_baseline": rvb, "summary_uz": _summary(trend, rvb)}


def _summary(trend: dict, rvb: dict) -> str:
    parts = []
    if rvb.get("t_mean_delta") is not None:
        word = "issiqroq" if rvb["t_mean_delta"] > 0 else "salqinroq"
        parts.append(
            f"So'nggi o'n yillik ({rvb['period']}) 1991–2020 bazasiga nisbatan o'rtacha {abs(rvb['t_mean_delta']):.1f}°C {word}."
        )
    if rvb.get("hot_days_delta") is not None:
        parts.append(f">35°C kunlar soni yiliga o'rtacha {rvb['hot_days_delta']:+.1f} kunga o'zgargan.")
    if rvb.get("precip_delta_pct") is not None:
        parts.append(f"Yillik yog'in {rvb['precip_delta_pct']:+.1f}% ga o'zgargan.")
    if trend.get("t_mean_per_decade") is not None:
        parts.append(f"Uzoq muddatli trend: har 10 yilda {trend['t_mean_per_decade']:+.2f}°C.")
    parts.append("Manba: NASA POWER (MERRA-2), ~50 km grid katagi — hudud foni, dala nuqtasi emas.")
    return " ".join(parts)


def monthly_baseline(daily: dict[date, dict]) -> list[dict]:
    """1991–2020 bo'yicha oylik harorat o'rtachasi va oylik yog'in yig'indisi (mean/std)."""
    t_by_month: dict[int, list[float]] = defaultdict(list)
    p_by_ym: dict[tuple[int, int], float] = defaultdict(float)
    for d, v in daily.items():
        if not (BASELINE[0] <= d.year <= BASELINE[1]):
            continue
        if v.get("T2M") is not None:
            t_by_month[d.month].append(v["T2M"])
        if v.get("PRECTOTCORR") is not None:
            p_by_ym[(d.year, d.month)] += v["PRECTOTCORR"]
    rows = []
    for m in range(1, 13):
        if t_by_month[m]:
            rows.append({"variable": "T2M", "month": m, "mean": statistics.fmean(t_by_month[m]),
                         "std": statistics.pstdev(t_by_month[m])})
        p = [val for (y, mm), val in p_by_ym.items() if mm == m]
        if p:
            rows.append({"variable": "PRECTOTCORR_MONTH", "month": m, "mean": statistics.fmean(p),
                         "std": statistics.pstdev(p)})
    return rows


def season_scenarios(daily: dict[date, dict], crop: dict, lat: float, planting_month_day: tuple[int, int],
                     years_back: int = 20) -> list[Scenario]:
    """Har bir o'tgan yil uchun ekin mavsumidagi ETc (Hargreaves ET0 × Kc) va samarali yog'inni hisoblab,
    suv tanqisligi bo'yicha quruq (80-persentil), o'rtacha (median), nam (20-persentil) yillarni tanlaydi."""
    if not daily:
        return []
    last_year = max(d.year for d in daily)
    per_year = []
    length = knowledge.season_length(crop)
    for year in range(last_year - years_back, last_year + 1):
        try:
            start = date(year, *planting_month_day)
        except ValueError:
            continue
        end = start + timedelta(days=length)
        if end > max(daily):
            continue
        etc = 0.0
        monthly_p: dict[tuple[int, int], float] = defaultdict(float)
        ok = True
        d = start
        while d < end:
            v = daily.get(d)
            if not v or v.get("T2M_MAX") is None or v.get("T2M_MIN") is None:
                ok = False
                break
            ra = extraterrestrial_radiation(lat, d.timetuple().tm_yday)
            kc = knowledge.stage_on(crop, start, d).kc
            etc += kc * hargreaves_et0(v["T2M_MIN"], v["T2M_MAX"], ra)
            monthly_p[(d.year, d.month)] += v.get("PRECTOTCORR") or 0.0
            d += timedelta(days=1)
        if not ok:
            continue
        peff = sum(monthly_effective_rain(p) for p in monthly_p.values())
        per_year.append((etc - peff, etc, peff))
    if len(per_year) < 3:
        return []
    per_year.sort()
    n = len(per_year)

    def pick(q: float) -> tuple[float, float, float]:
        return per_year[min(n - 1, max(0, round(q * (n - 1))))]

    wet, normal, dry = pick(0.2), pick(0.5), pick(0.8)
    return [
        Scenario("dry", dry[1], dry[2]),
        Scenario("normal", normal[1], normal[2]),
        Scenario("wet", wet[1], wet[2]),
    ]
