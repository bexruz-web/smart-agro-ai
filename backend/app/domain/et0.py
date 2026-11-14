"""FAO-56 Penman-Monteith bo'yicha kunlik etalon evapotranspiratsiya (ET0), mm/kun.

Formulalar FAO-56 (Allen va b., 1998) 2–3-boblaridan. Natija FAO-56 18-misoli bilan testlangan.
"""
import math


def sat_vapour_pressure(t: float) -> float:
    """e°(T), kPa — FAO-56 11-tenglama."""
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def slope_vapour_curve(t: float) -> float:
    """Δ, kPa/°C — FAO-56 13-tenglama."""
    return 4098 * sat_vapour_pressure(t) / (t + 237.3) ** 2


def atmospheric_pressure(elevation_m: float) -> float:
    """P, kPa — FAO-56 7-tenglama."""
    return 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26


def extraterrestrial_radiation(lat_deg: float, doy: int) -> float:
    """Ra, MJ/m²/kun — FAO-56 21-tenglama."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )


def actual_vapour_pressure_from_rh(t_min: float, t_max: float, rh_mean: float) -> float:
    """ea — FAO-56 19-tenglama (faqat o'rtacha nisbiy namlik ma'lum bo'lsa)."""
    es = (sat_vapour_pressure(t_max) + sat_vapour_pressure(t_min)) / 2
    return rh_mean / 100 * es


def et0_penman_monteith(
    t_min: float,
    t_max: float,
    ea: float,
    rs: float,
    u2: float,
    lat_deg: float,
    doy: int,
    elevation_m: float,
    g: float = 0.0,
) -> float:
    """ET0 (mm/kun). rs — quyosh radiatsiyasi MJ/m²/kun, u2 — 2 m balandlikdagi shamol m/s."""
    t_mean = (t_max + t_min) / 2
    delta = slope_vapour_curve(t_mean)
    gamma = 0.000665 * atmospheric_pressure(elevation_m)  # 8-tenglama
    es = (sat_vapour_pressure(t_max) + sat_vapour_pressure(t_min)) / 2  # 12-tenglama
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = (0.75 + 2e-5 * elevation_m) * ra  # 37-tenglama
    rns = (1 - 0.23) * rs  # 38-tenglama
    sigma = 4.903e-9
    tmax_k4 = (t_max + 273.16) ** 4
    tmin_k4 = (t_min + 273.16) ** 4
    rs_rso = min(1.0, rs / rso) if rso > 0 else 0.5
    rnl = sigma * (tmax_k4 + tmin_k4) / 2 * (0.34 - 0.14 * math.sqrt(max(ea, 0))) * (1.35 * rs_rso - 0.35)  # 39
    rn = rns - rnl
    num = 0.408 * delta * (rn - g) + gamma * 900 / (t_mean + 273) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, num / den)
