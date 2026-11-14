"""Faol harorat yig'indisi (GDD)."""


def gdd_day(t_min: float, t_max: float, t_base: float) -> float:
    return max(0.0, (t_min + t_max) / 2 - t_base)


def gdd_sum(days: list[tuple[float, float]], t_base: float) -> float:
    return sum(gdd_day(tmin, tmax, t_base) for tmin, tmax in days)
