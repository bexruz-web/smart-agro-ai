"""Dala yaratish/yangilash: geometriya validatsiyasi, PostGIS'da geodezik maydon, ustma-ust tushish tekshiruvi."""
import json
import math

from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Field
from app.domain.geo import MAX_AREA_HA, MIN_AREA_HA, GeometryError, validate_polygon_geojson


async def measure(session: AsyncSession, geojson: dict) -> dict:
    """PostGIS bo'yicha geodezik maydon (ga), centroid va bbox."""
    poly = validate_polygon_geojson(geojson)
    gj = json.dumps({"type": "Polygon", "coordinates": [list(map(list, poly.exterior.coords))]})
    row = (await session.execute(text(
        """
        WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326) AS geom)
        SELECT ST_IsValid(geom), ST_Area(geom::geography) / 10000.0,
               ST_Y(ST_Centroid(geom)), ST_X(ST_Centroid(geom)),
               ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
        FROM g
        """), {"gj": gj})).one()
    valid, area, clat, clon, xmin, ymin, xmax, ymax = row
    if not valid:
        raise GeometryError("Invalid polygon (PostGIS ST_IsValid)")
    if not (MIN_AREA_HA <= area <= MAX_AREA_HA):
        raise GeometryError(f"Area {area:.2f} ha is outside the allowed range {MIN_AREA_HA}–{MAX_AREA_HA} ha")
    return {"wkt_geojson": gj, "area_ha": round(area, 4), "centroid_lat": clat, "centroid_lon": clon,
            "bbox": [xmin, ymin, xmax, ymax]}


def square_geojson(lat: float, lon: float, area_ha: float) -> dict:
    """Fermer kiritgan maydonga teng taxminiy kvadrat (markazi — xaritada belgilangan nuqta), xaritada ko'rsatish uchun."""
    half = math.sqrt(area_ha * 10000) / 2
    dlat = half / 111_320
    dlon = half / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


async def overlap_warnings(session: AsyncSession, farmer_id: int, gj: str, exclude_id: int | None = None) -> list[str]:
    q = text(
        """
        SELECT name FROM fields
        WHERE farmer_id = :fid AND (CAST(:ex AS INTEGER) IS NULL OR id <> CAST(:ex AS INTEGER))
          AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
          AND ST_Area(ST_Intersection(geom, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))::geography) > 100
        """
    )
    names = (await session.execute(q, {"fid": farmer_id, "ex": exclude_id, "gj": gj})).scalars().all()
    return [f"Boshqa dalangiz bilan ustma-ust tushadi: {n}" for n in names]


async def field_geojson(session: AsyncSession, field_id: int) -> dict:
    gj = await session.scalar(select(ST_AsGeoJSON(Field.geom)).where(Field.id == field_id))
    return json.loads(gj)


async def field_bbox(session: AsyncSession, field_id: int) -> list[float]:
    row = (await session.execute(
        select(func.ST_XMin(Field.geom), func.ST_YMin(Field.geom), func.ST_XMax(Field.geom), func.ST_YMax(Field.geom))
        .where(Field.id == field_id))).one()
    return [float(x) for x in row]
