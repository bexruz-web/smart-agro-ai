"""Ildiz zonasi suv balansi (FAO-56, 8-bob, soddalashtirilgan) va sug'orish tavsiyasi.

Dr,i = Dr,i−1 − (P − RO)i − Ii + ETc,i      (CR va DP hisobga olinmaydi — soddalashtirish)
TAW  = 1000·(θFC − θWP)·Zr ;  RAW = p·TAW ;  Ks = (TAW − Dr)/((1 − p)·TAW) agar Dr > RAW
"""
from dataclasses import dataclass, field


@dataclass
class SoilWater:
    theta_fc: float
    theta_wp: float
    root_depth_m: float
    p: float

    @property
    def taw_mm(self) -> float:
        return 1000 * (self.theta_fc - self.theta_wp) * self.root_depth_m

    @property
    def raw_mm(self) -> float:
        return self.p * self.taw_mm


def effective_rain(p_mm: float) -> float:
    """Kunlik samarali yog'in: kichik yog'inlar (<5 mm) asosan bug'lanadi, qolganidan 80%.
    Soddalashtirilgan qoida (taxmin) — oylik FAO/AGLW formulasining kunlik analogi."""
    return 0.0 if p_mm < 5 else 0.8 * p_mm


def monthly_effective_rain(p_month_mm: float) -> float:
    """FAO/AGLW (CROPWAT 'dependable rain') formulasi, oylik yog'in uchun."""
    if p_month_mm <= 70:
        return max(0.0, 0.6 * p_month_mm - 10)
    return 0.8 * p_month_mm - 24


def ks_factor(depletion: float, sw: SoilWater) -> float:
    if depletion <= sw.raw_mm:
        return 1.0
    return max(0.0, (sw.taw_mm - depletion) / ((1 - sw.p) * sw.taw_mm))


@dataclass
class BalanceDay:
    day: str
    etc: float
    eta: float
    rain_eff: float
    irrigation: float
    depletion: float
    ks: float


@dataclass
class BalanceResult:
    days: list[BalanceDay] = field(default_factory=list)

    @property
    def depletion(self) -> float:
        return self.days[-1].depletion if self.days else 0.0


def run_balance(
    days: list[dict], sw: SoilWater, start_depletion: float = 0.0
) -> BalanceResult:
    """days: [{"day", "etc", "rain", "irrigation"}] (mm). Natija: kunlik depletion va Ks."""
    result = BalanceResult()
    dr = max(0.0, min(start_depletion, sw.taw_mm))
    for d in days:
        ks = ks_factor(dr, sw)
        eta = ks * d["etc"]
        rain_eff = effective_rain(d.get("rain", 0.0))
        irr = d.get("irrigation", 0.0)
        dr = dr - rain_eff - irr + eta
        dr = max(0.0, min(dr, sw.taw_mm))  # ortiqcha suv drenajga ketadi (DP)
        result.days.append(BalanceDay(d["day"], d["etc"], eta, rain_eff, irr, dr, ks))
    return result


def depletion_from_vwc(vwc_pct: float, sw: SoilWater) -> float:
    """Sensor hajmiy namligidan (VWC %) ildiz zonasi tanqisligini taxmin qilish.
    Sensor bitta chuqurlikda o'lchaydi — butun ildiz zonasi bir xil deb taxmin qilinadi."""
    theta = vwc_pct / 100
    return max(0.0, min(sw.taw_mm, 1000 * (sw.theta_fc - theta) * sw.root_depth_m))


def irrigation_mm_to_m3_ha(mm: float) -> float:
    """1 mm suv qatlami = 10 m³/ga."""
    return mm * 10
