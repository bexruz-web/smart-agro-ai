"""API sxemalari (Pydantic v2) — docs/API_CONTRACT.md bilan mos."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class FarmerOut(BaseModel):
    id: int
    telegram_id: int
    first_name: str | None
    username: str | None
    report_interval_hours: int
    quiet_hours_start: int | None
    quiet_hours_end: int | None
    farm_location: LatLon | None
    consent_at: datetime | None
    is_demo: bool


class AuthTelegramIn(BaseModel):
    init_data: str = Field(min_length=10, max_length=4096)


class AuthOut(BaseModel):
    access_token: str
    farmer: FarmerOut


class MePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_interval_hours: Literal[1, 2, 4, 6, 12, 24] | None = None
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)
    farm_location: LatLon | None = None
    consent: bool | None = None
    clear_quiet_hours: bool | None = None


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class FieldIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    geometry: GeoJSONPolygon
    drawing_method: Literal["quad", "polygon"] = "polygon"
    crop: str | None = None
    planting_date: date | None = None
    soil_texture: str | None = None
    water_available_m3_ha: float | None = Field(default=None, ge=0, le=50000)
    soil_ph: float | None = Field(default=None, ge=3, le=10)
    soil_ec_ds_m: float | None = Field(default=None, ge=0, le=30)

    @field_validator("planting_date")
    @classmethod
    def not_far_future(cls, v: date | None):
        if v and v.year > date.today().year + 1:
            raise ValueError("Ekish sanasi juda uzoq kelajakda")
        return v


class FieldPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    geometry: GeoJSONPolygon | None = None
    drawing_method: Literal["quad", "polygon"] | None = None
    crop: str | None = None
    planting_date: date | None = None
    soil_texture: str | None = None
    water_available_m3_ha: float | None = Field(default=None, ge=0, le=50000)
    soil_ph: float | None = Field(default=None, ge=3, le=10)
    soil_ec_ds_m: float | None = Field(default=None, ge=0, le=30)


class FieldOut(BaseModel):
    id: int
    name: str
    geometry: dict
    area_ha: float
    centroid: LatLon
    bbox: list[float]
    drawing_method: str
    crop: str | None
    crop_name_uz: str | None
    planting_date: date | None
    soil_texture: str | None
    water_available_m3_ha: float | None
    soil_ph: float | None
    soil_ec_ds_m: float | None
    created_at: datetime
    is_demo: bool
    warnings: list[str] = []


class FeedbackIn(BaseModel):
    action: Literal["done", "later", "rejected", "useful", "not_useful"]
    comment: str | None = Field(default=None, max_length=1000)


class SeasonIn(BaseModel):
    crop: str
    planting_date: date | None = None


class HarvestIn(BaseModel):
    harvest_date: date
    yield_t_ha: float = Field(ge=0, le=200)
    quality: Literal["a'lo", "yaxshi", "o'rta", "past"] | None = None
    water_used_m3: float | None = Field(default=None, ge=0)
    fertilizers: str | None = Field(default=None, max_length=2000)
    problems: str | None = Field(default=None, max_length=2000)


class EventIn(BaseModel):
    type: Literal["irrigation", "fertilizer", "tillage", "pesticide", "other"]
    date: date
    amount: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    field_id: int | None = None


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    field_id: int


class Reading(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ts: datetime
    soil_moisture_raw: float | None = None
    soil_moisture_vwc: float | None = None
    soil_temp_c: float | None = None
    air_temp_c: float | None = None
    air_rh: float | None = None
    rain: bool | None = None
    light_lux: float | None = None


class IotPayload(BaseModel):
    device_id: str = Field(max_length=64)
    fw: str | None = Field(default=None, max_length=32)
    seq: int = Field(ge=0)
    rssi: int | None = None
    battery_v: float | None = None
    readings: list[Reading] = Field(min_length=1, max_length=200)
