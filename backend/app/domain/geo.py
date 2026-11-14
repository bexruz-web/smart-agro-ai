"""Dala geometriyasi validatsiyasi va NASA POWER grid kataklari."""
from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity

MIN_AREA_HA = 0.05
MAX_AREA_HA = 5000.0
POWER_LAT_STEP = 0.5
POWER_LON_STEP = 0.625


class GeometryError(ValueError):
    pass


def validate_polygon_geojson(geojson: dict) -> Polygon:
    if not isinstance(geojson, dict) or geojson.get("type") != "Polygon":
        raise GeometryError("Geometriya GeoJSON Polygon bo'lishi kerak")
    rings = geojson.get("coordinates") or []
    if len(rings) != 1:
        raise GeometryError("Polygon bitta tashqi chegaradan iborat bo'lishi kerak (teshiklarsiz)")
    ring = [tuple(map(float, p[:2])) for p in rings[0]]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])  # yopilmagan halqani yopamiz
    distinct = {(round(x, 7), round(y, 7)) for x, y in ring}
    if len(distinct) < 3:
        raise GeometryError("Kamida 3 ta har xil nuqta kerak")
    for lon, lat in ring:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise GeometryError("Koordinatalar noto'g'ri: [uzunlik, kenglik] tartibida bo'lishi kerak")
    poly = shape({"type": "Polygon", "coordinates": [ring]})
    if not poly.is_valid:
        reason = explain_validity(poly)
        if "Self-intersection" in reason:
            raise GeometryError("Polygon o'z-o'zini kesib o'tmoqda — nuqtalar tartibini tekshiring")
        raise GeometryError(f"Polygon noto'g'ri: {reason}")
    return poly


def grid_key(lat: float, lon: float) -> str:
    """NASA POWER meteorologik grid katagi (½° × ⅝°) — bir katakdagi dalalar keshni bo'lishadi."""
    glat = round(lat / POWER_LAT_STEP) * POWER_LAT_STEP
    glon = round(lon / POWER_LON_STEP) * POWER_LON_STEP
    return f"{glat:.2f}:{glon:.3f}"
