/** Add / edit field form: values, validation (localized messages) and the API payload. */
import type { Field, FieldInput } from '../api/types'
import { AREA_MAX_HA, AREA_MIN_HA, NAME_MAX_LENGTH } from '../config'
import { getLang, type Lang, type TFunction } from '../i18n'
import { decimalToInput, fmtNum, parseDecimal } from './format'
import { isValidLatLon, polygonCentroid, toGeoJsonPolygon, usablePolygon, type LatLon } from './geo'
import { isValidDateOnly, todayTashkent } from './time'

export interface FieldFormValues {
  name: string
  crop: string | null
  area: string
  plantingDate: string
  soil: string | null
  irrigation: string | null
  water: string | null
  location: LatLon | null
  /** Drawn boundary (3+ vertices). If set, it is sent as the GeoJSON geometry; without a pin its centroid is the location. */
  polygon: LatLon[] | null
}

export type FieldFormKey = keyof FieldFormValues
export type FieldFormErrors = Partial<Record<FieldFormKey, string>>

/** Order of the form steps (used to scroll to the first error). */
export const FORM_ORDER: FieldFormKey[] = ['name', 'crop', 'area', 'plantingDate', 'soil', 'irrigation', 'water', 'location']

export const EMPTY_FORM: FieldFormValues = {
  name: '',
  crop: null,
  area: '',
  plantingDate: '',
  soil: null,
  irrigation: null,
  water: null,
  location: null,
  polygon: null,
}

export function formFromField(f: Field, lang: Lang = getLang()): FieldFormValues {
  return {
    name: f.name ?? '',
    crop: f.crop ?? null,
    area: decimalToInput(f.area_ha, lang),
    plantingDate: f.planting_date ?? '',
    soil: f.soil_texture ?? null,
    irrigation: f.irrigation_type ?? null,
    water: f.water_source ?? null,
    location: isValidLatLon(f.location) ? f.location : null,
    polygon: null,
  }
}

export function validateFieldForm(
  v: FieldFormValues,
  t: TFunction,
  today: string = todayTashkent(),
  lang: Lang = getLang(),
): { errors: FieldFormErrors; input: FieldInput | null } {
  const errors: FieldFormErrors = {}
  const name = v.name.trim()
  if (!name) errors.name = t('err.nameRequired')
  else if (name.length > NAME_MAX_LENGTH) errors.name = t('err.nameLong', { max: NAME_MAX_LENGTH })

  if (!v.crop) errors.crop = t('err.cropRequired')

  const area = parseDecimal(v.area)
  if (!v.area.trim()) errors.area = t('err.areaRequired')
  else if (area === null) errors.area = t('err.areaNumber')
  else if (area < AREA_MIN_HA || area > AREA_MAX_HA)
    errors.area = t('err.areaRange', { min: fmtNum(AREA_MIN_HA, 2, lang), max: fmtNum(AREA_MAX_HA, 0, lang) })

  if (!v.plantingDate || !isValidDateOnly(v.plantingDate)) errors.plantingDate = t('err.dateRequired')
  // Same rule as the server: not later than the end of next year (next crop may be planned ahead).
  else if (v.plantingDate > `${Number(today.slice(0, 4)) + 1}-12-31`) errors.plantingDate = t('err.dateFuture')

  if (!v.soil) errors.soil = t('err.soilRequired')
  if (!v.irrigation) errors.irrigation = t('err.irrigationRequired')
  if (!v.water) errors.water = t('err.waterRequired')
  const polygon = usablePolygon(v.polygon)
  if (!isValidLatLon(v.location) && !polygon) errors.location = t('err.locationRequired')

  if (Object.keys(errors).length) return { errors, input: null }

  // No pin (boundary drawn instead): the field is placed at the polygon's centroid.
  const loc = isValidLatLon(v.location) ? v.location : polygonCentroid(polygon!)
  return {
    errors,
    input: {
      name,
      crop: v.crop!,
      area_ha: Math.round(area! * 10000) / 10000,
      planting_date: v.plantingDate,
      soil_texture: v.soil!,
      irrigation_type: v.irrigation!,
      water_source: v.water!,
      location: { lat: round6(loc.lat), lon: round6(loc.lon) },
      ...(polygon ? { geometry: toGeoJsonPolygon(polygon) } : {}),
    },
  }
}

const round6 = (n: number) => Math.round(n * 1e6) / 1e6
