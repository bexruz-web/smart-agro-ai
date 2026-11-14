/**
 * Dala qo'shish / tahrirlash (MAP-1, MAP-2, MAP-4).
 *  (a) "4 burchak": tap 4 points, type coordinates, or add the current GPS position as a corner.
 *  (b) "Polygon": free drawing with Terra Draw (vertex editing + undo).
 * Client-side validation is a preview; the server is authoritative (area, overlap warnings).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { createField, getCrops, getField, getFields, getSoilTextures, updateField } from '../api/endpoints'
import type { DrawingMethod, Field, FieldInput } from '../api/types'
import { useAuth } from '../auth'
import { Card, ErrorBox, FormRow, Loading, Page, Segmented } from '../components/ui'
import { DEFAULT_CENTER, DEFAULT_ZOOM } from '../config'
import { useAsync } from '../hooks/useAsync'
import { useMainButton } from '../hooks/useTelegramButtons'
import { MapView } from '../map/MapView'
import type { DrawState, MapController, MapPolygon, PolygonDrawSession } from '../map/types'
import { getCurrentLocation, haptic } from '../telegram'
import {
  formatHa,
  fromGeoJsonPolygon,
  isValidLatLon,
  orderQuad,
  parseCoordinate,
  parseLatLonPair,
  toGeoJsonPolygon,
  validatePolygon,
  type LatLon,
} from '../utils/geo'

interface Slot {
  lat: string
  lon: string
  accuracy: number | null
  source: 'map' | 'gps' | 'manual' | null
}

const EMPTY_SLOT: Slot = { lat: '', lon: '', accuracy: null, source: null }
const emptySlots = (): Slot[] => [0, 1, 2, 3].map(() => ({ ...EMPTY_SLOT }))
const slotFrom = (p: LatLon, source: Slot['source'], accuracy: number | null = null): Slot => ({
  lat: p.lat.toFixed(6),
  lon: p.lon.toFixed(6),
  accuracy,
  source,
})

function slotPoint(s: Slot): LatLon | null {
  const lat = parseCoordinate(s.lat)
  const lon = parseCoordinate(s.lon)
  if (lat === null || lon === null) return null
  const p = { lat, lon }
  return isValidLatLon(p) ? p : null
}

function slotError(s: Slot): string | null {
  if (!s.lat.trim() && !s.lon.trim()) return null
  if (slotPoint(s)) return null
  return "Koordinata noto'g'ri (masalan 40.123456 va 67.123456)"
}

function parseOptionalNumber(s: string): number | null | 'invalid' {
  if (!s.trim()) return null
  const n = parseCoordinate(s)
  return n === null ? 'invalid' : n
}

export function FieldEditorPage() {
  const { id } = useParams()
  const fieldId = id ? Number(id) : null
  const isEdit = fieldId !== null
  const navigate = useNavigate()
  const { farmer } = useAuth()

  const crops = useAsync(getCrops, [])
  const soils = useAsync(getSoilTextures, [])
  const allFields = useAsync(getFields, [])
  const existing = useAsync<Field | null>(() => (fieldId ? getField(fieldId) : Promise.resolve(null)), [fieldId])

  if (isEdit && existing.loading) return <Page title="Dalani tahrirlash" back={true}><Loading /></Page>
  if (isEdit && existing.error) {
    return (
      <Page title="Dalani tahrirlash" back={true}>
        <ErrorBox error={existing.error} onRetry={existing.reload} />
      </Page>
    )
  }

  return (
    <Editor
      key={fieldId ?? 'new'}
      existing={existing.data ?? null}
      others={(allFields.data ?? []).filter((f) => f.id !== fieldId)}
      crops={crops.data ?? []}
      soils={soils.data ?? []}
      refsError={crops.error || soils.error}
      reloadRefs={() => {
        crops.reload()
        soils.reload()
      }}
      farmLocation={farmer.farm_location}
      onSaved={(f) => navigate(`/fields/${f.id}`, { replace: true })}
    />
  )
}

interface EditorProps {
  existing: Field | null
  others: Field[]
  crops: { key: string; name_uz: string; family_uz: string }[]
  soils: { key: string; name_uz: string }[]
  refsError: Error | null
  reloadRefs: () => void
  farmLocation: LatLon | null
  onSaved: (f: Field) => void
}

function Editor({ existing, others, crops, soils, refsError, reloadRefs, farmLocation, onSaved }: EditorProps) {
  const navigate = useNavigate()
  const existingPoints = useMemo(() => fromGeoJsonPolygon(existing?.geometry), [existing])
  const startAsQuad = existing ? existing.drawing_method === 'quad' && existingPoints.length === 4 : true

  // ---- geometry state
  const [mode, setMode] = useState<DrawingMethod>(startAsQuad ? 'quad' : 'polygon')
  const [slots, setSlots] = useState<Slot[]>(() =>
    startAsQuad && existing ? existingPoints.map((p) => slotFrom(p, 'manual')) : emptySlots(),
  )
  const [polyPoints, setPolyPoints] = useState<LatLon[] | null>(!startAsQuad ? existingPoints : null)
  const [drawState, setDrawState] = useState<DrawState>('idle')
  const [canUndo, setCanUndo] = useState(false)
  const [gpsBusy, setGpsBusy] = useState(false)
  const [gpsMsg, setGpsMsg] = useState<string | null>(null)
  const [paste, setPaste] = useState('')

  // ---- form state
  const [name, setName] = useState(existing?.name ?? '')
  const [nameTouched, setNameTouched] = useState(false)
  const [crop, setCrop] = useState(existing?.crop ?? '')
  const [plantingDate, setPlantingDate] = useState(existing?.planting_date ?? '')
  const [soil, setSoil] = useState(existing?.soil_texture ?? '')
  const [water, setWater] = useState(existing?.water_available_m3_ha != null ? String(existing.water_available_m3_ha) : '')
  const [ph, setPh] = useState(existing?.soil_ph != null ? String(existing.soil_ph) : '')
  const [ec, setEc] = useState(existing?.soil_ec_ds_m != null ? String(existing.soil_ec_ds_m) : '')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Field | null>(null)

  // ---- map
  const mapRef = useRef<MapController | null>(null)
  const sessionRef = useRef<PolygonDrawSession | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const polyPointsRef = useRef(polyPoints)
  polyPointsRef.current = polyPoints

  const quadPoints = useMemo(() => slots.map(slotPoint).filter((p): p is LatLon => p !== null), [slots])
  const orderedQuad = useMemo(() => (quadPoints.length >= 3 ? orderQuad(quadPoints) : quadPoints), [quadPoints])

  const geometryPoints: LatLon[] | null = mode === 'quad' ? (quadPoints.length === 4 ? orderedQuad : null) : polyPoints
  const validation = useMemo(() => (geometryPoints ? validatePolygon(geometryPoints) : null), [geometryPoints])

  const onMapReady = useCallback(
    (map: MapController) => {
      mapRef.current = map
      if (existingPoints.length) map.fitTo(existingPoints)
      else if (farmLocation) map.setView(farmLocation, 15)
      setMapReady(true)
    },
    [existingPoints, farmLocation],
  )

  // Quad mode: map taps fill the first empty corner slot.
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    if (mode !== 'quad') {
      map.onClick(null)
      return
    }
    map.onClick((p) => {
      setSlots((prev) => {
        const i = prev.findIndex((s) => !slotPoint(s))
        if (i < 0) return prev
        const next = [...prev]
        next[i] = slotFrom(p, 'map')
        return next
      })
    })
    return () => map.onClick(null)
  }, [mapReady, mode])

  // Polygon mode: run a Terra Draw session while active.
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map || mode !== 'polygon') return
    const session = map.startPolygonDrawing(
      {
        onChange: (pts) => setPolyPoints(pts),
        onState: (state, undo) => {
          setDrawState(state)
          setCanUndo(undo)
        },
      },
      polyPointsRef.current,
    )
    sessionRef.current = session
    return () => {
      session.destroy()
      sessionRef.current = null
    }
  }, [mapReady, mode])

  // Static layers: other fields (to see overlaps) + quad preview and corner markers.
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    const layers: MapPolygon[] = others.map((f) => ({
      id: `field-${f.id}`,
      points: fromGeoJsonPolygon(f.geometry),
      variant: 'other',
      label: f.name,
    }))
    if (mode === 'quad' && orderedQuad.length >= 3) {
      layers.push({ id: 'quad', points: orderedQuad, variant: validation && !validation.ok ? 'invalid' : 'preview' })
    }
    map.setPolygons(layers)
    map.setMarkers(
      mode === 'quad'
        ? slots
            .map((s, i) => ({ s, i, p: slotPoint(s) }))
            .filter((x) => x.p)
            .map((x) => ({ id: `c${x.i}`, position: x.p!, label: String(x.i + 1), accuracyM: x.s.accuracy }))
        : [],
    )
  }, [mapReady, mode, others, orderedQuad, slots, validation])

  // When the 4th corner is entered (typed / pasted / GPS), bring the whole quad into view.
  const quadCount = quadPoints.length
  const quadRef = useRef(orderedQuad)
  quadRef.current = orderedQuad
  useEffect(() => {
    if (mapReady && mode === 'quad' && quadCount === 4) mapRef.current?.fitTo(quadRef.current)
  }, [mapReady, mode, quadCount])

  const switchMode = (m: DrawingMethod) => {
    if (m === mode) return
    if (m === 'polygon' && quadPoints.length >= 3) setPolyPoints(orderedQuad)
    if (m === 'quad' && polyPoints && polyPoints.length === 4) setSlots(polyPoints.map((p) => slotFrom(p, 'manual')))
    setMode(m)
  }

  const updateSlot = (i: number, patch: Partial<Slot>) =>
    setSlots((prev) => prev.map((s, j) => (j === i ? { ...s, ...patch, source: 'manual', accuracy: null } : s)))
  const clearSlot = (i: number) => setSlots((prev) => prev.map((s, j) => (j === i ? { ...EMPTY_SLOT } : s)))
  const firstEmpty = slots.findIndex((s) => !slotPoint(s))

  const addPasted = () => {
    const p = parseLatLonPair(paste)
    if (!p || firstEmpty < 0) return
    setSlots((prev) => prev.map((s, j) => (j === firstEmpty ? slotFrom(p, 'manual') : s)))
    setPaste('')
  }

  const addGpsCorner = async () => {
    if (firstEmpty < 0) return
    setGpsBusy(true)
    setGpsMsg(null)
    try {
      const fix = await getCurrentLocation()
      const p = { lat: fix.lat, lon: fix.lon }
      const idx = firstEmpty
      setSlots((prev) => prev.map((s, j) => (j === idx ? slotFrom(p, 'gps', fix.accuracy) : s)))
      mapRef.current?.setView(p, 18)
      const acc = fix.accuracy !== null ? Math.round(fix.accuracy) : null
      setGpsMsg(
        acc === null
          ? `${idx + 1}-burchak qo'shildi (aniqlik noma'lum)`
          : acc > 20
            ? `${idx + 1}-burchak qo'shildi, lekin aniqlik past: ±${acc} m. Ochiq joyda biroz kutib, qayta urinib ko'ring.`
            : `${idx + 1}-burchak qo'shildi · aniqlik ±${acc} m`,
      )
      haptic('success')
    } catch (e) {
      setGpsMsg(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setGpsBusy(false)
    }
  }

  // ---- form validation
  const waterVal = parseOptionalNumber(water)
  const phVal = parseOptionalNumber(ph)
  const ecVal = parseOptionalNumber(ec)
  const waterErr = waterVal === 'invalid' || (typeof waterVal === 'number' && waterVal < 0) ? "Musbat son kiriting (m³/ga)" : null
  const phErr = phVal === 'invalid' || (typeof phVal === 'number' && (phVal < 3 || phVal > 10)) ? 'pH 3 dan 10 gacha bo\'lishi kerak' : null
  const ecErr = ecVal === 'invalid' || (typeof ecVal === 'number' && (ecVal < 0 || ecVal > 30)) ? "ECe 0 dan 30 dS/m gacha bo'lishi kerak" : null
  const nameErr = name.trim() ? null : 'Dala nomini kiriting'
  const geometryOk = !!geometryPoints && !!validation?.ok
  const canSave = geometryOk && !nameErr && !waterErr && !phErr && !ecErr && !saving

  const save = async () => {
    if (!canSave || !geometryPoints) return
    setSaving(true)
    setSaveError(null)
    const body: FieldInput = {
      name: name.trim(),
      geometry: toGeoJsonPolygon(geometryPoints),
      drawing_method: mode,
      crop: crop || null,
      planting_date: plantingDate || null,
      soil_texture: soil || null,
      water_available_m3_ha: typeof waterVal === 'number' ? waterVal : null,
      soil_ph: typeof phVal === 'number' ? phVal : null,
      soil_ec_ds_m: typeof ecVal === 'number' ? ecVal : null,
    }
    try {
      const f = existing ? await updateField(existing.id, body) : await createField(body)
      haptic('success')
      if (f.warnings && f.warnings.length) setSaved(f)
      else onSaved(f)
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : 'Saqlashda xatolik')
      haptic('error')
    } finally {
      setSaving(false)
    }
  }

  const native = useMainButton(saving ? 'Saqlanmoqda…' : 'Saqlash', save, { visible: !saved, enabled: canSave, progress: saving })

  if (saved) {
    return (
      <Page title="Dala saqlandi" back="/">
        <Card title="Server ogohlantirishlari" tone="warning">
          <ul className="bullets">
            {saved.warnings!.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
          <p className="muted">
            Dala saqlandi: {formatHa(saved.area_ha)} ga (server hisobi). Kerak bo'lsa chegarani tahrirlang.
          </p>
        </Card>
        <div className="btn-row">
          <button type="button" className="btn btn--primary" onClick={() => onSaved(saved)}>
            Dala paneliga o'tish
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => navigate(`/fields/${saved.id}/edit`, { replace: true })}>
            Chegarani tahrirlash
          </button>
        </div>
      </Page>
    )
  }

  const center = existingPoints[0] ?? farmLocation ?? DEFAULT_CENTER
  const zoom = existingPoints.length || farmLocation ? 15 : DEFAULT_ZOOM

  return (
    <Page title={existing ? 'Dalani tahrirlash' : "Dala qo'shish"} back={true}>
      <Segmented
        ariaLabel="Chizish usuli"
        value={mode}
        onChange={switchMode}
        options={[
          { value: 'quad', label: '4 burchak' },
          { value: 'polygon', label: 'Polygon' },
        ]}
      />

      <MapView className="map--large" options={{ center, zoom }} onReady={onMapReady} />

      {mode === 'quad' ? (
        <div className="draw-panel">
          <p className="muted">
            Dalaning 4 burchagini xaritada bosing, koordinatani yozing yoki burchakda turib GPS orqali qo'shing.
          </p>
          <button type="button" className="btn btn--secondary btn--block" onClick={addGpsCorner} disabled={gpsBusy || firstEmpty < 0}>
            {gpsBusy ? 'GPS aniqlanmoqda…' : "📍 Shu nuqtani qo'shish (GPS)"}
          </button>
          {gpsMsg && <div className="muted">{gpsMsg}</div>}
          <div className="corner-list">
            {slots.map((s, i) => {
              const err = slotError(s)
              return (
                <div key={i} className={`corner ${err ? 'corner--error' : ''}`}>
                  <span className="corner__num">{i + 1}</span>
                  <input
                    className="input input--compact"
                    inputMode="decimal"
                    placeholder="Kenglik (lat)"
                    aria-label={`${i + 1}-burchak kengligi`}
                    value={s.lat}
                    onChange={(e) => updateSlot(i, { lat: e.target.value })}
                  />
                  <input
                    className="input input--compact"
                    inputMode="decimal"
                    placeholder="Uzunlik (lon)"
                    aria-label={`${i + 1}-burchak uzunligi`}
                    value={s.lon}
                    onChange={(e) => updateSlot(i, { lon: e.target.value })}
                  />
                  <button
                    type="button"
                    className="btn btn--ghost btn--icon"
                    aria-label={`${i + 1}-burchakni o'chirish`}
                    onClick={() => clearSlot(i)}
                    disabled={!s.lat && !s.lon}
                  >
                    ✕
                  </button>
                  {(s.source === 'gps' || err) && (
                    <div className="corner__meta">
                      {err ?? (s.accuracy !== null ? `GPS · ±${Math.round(s.accuracy)} m` : 'GPS')}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {firstEmpty >= 0 && (
            <div className="paste-row">
              <input
                className="input"
                placeholder="Yoki juftlikni joylang: 40.1234, 67.8123"
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPasted()}
              />
              <button type="button" className="btn btn--secondary" onClick={addPasted} disabled={!parseLatLonPair(paste)}>
                Qo'shish
              </button>
            </div>
          )}
          <p className="muted small">
            Eslatma: 4 ta ixtiyoriy nuqta to'g'ri to'rtburchak emas, ixtiyoriy to'rtburchak hosil qiladi va shunday saqlanadi.
          </p>
        </div>
      ) : (
        <div className="draw-panel">
          <p className="muted">
            {drawState === 'idle' && "Dala chegarasi bo'ylab xaritaga ketma-ket bosing."}
            {drawState === 'drawing' && "Yopish uchun birinchi nuqtaga bosing yoki «Yakunlash» tugmasini bosing."}
            {drawState === 'done' && "Uchlarni surib tahrirlang; qirra o'rtasidagi nuqtani sursangiz yangi uch qo'shiladi."}
          </p>
          <div className="btn-row">
            <button type="button" className="btn btn--secondary" onClick={() => sessionRef.current?.undo()} disabled={!canUndo}>
              ↶ Bekor qilish
            </button>
            {drawState === 'drawing' && (
              <button type="button" className="btn btn--secondary" onClick={() => sessionRef.current?.finish()}>
                ✔ Yakunlash
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={() => sessionRef.current?.clear()} disabled={drawState === 'idle'}>
              🗑 Qaytadan chizish
            </button>
          </div>
        </div>
      )}

      <div className={`area-preview ${validation && !validation.ok ? 'area-preview--error' : ''}`}>
        {!geometryPoints && (
          <span className="muted">
            {mode === 'quad' ? `4 ta burchak kerak (hozir ${quadPoints.length} ta)` : 'Polygon hali chizilmagan'}
          </span>
        )}
        {validation && validation.areaHa !== null && (
          <div>
            Taxminiy maydon: <strong>{formatHa(validation.areaHa)} ga</strong>{' '}
            <span className="muted small">(aniq maydonni server hisoblaydi)</span>
          </div>
        )}
        {validation?.errors.map((e) => (
          <div key={e} className="form-row__error">
            {e}
          </div>
        ))}
      </div>

      <Card title="Dala ma'lumotlari">
        {refsError && <ErrorBox error={refsError} onRetry={reloadRefs} />}
        <FormRow label="Dala nomi *" error={nameTouched ? nameErr : null} htmlFor="f-name">
          <input
            id="f-name"
            className="input"
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => setNameTouched(true)}
            placeholder="Masalan: Shimoliy dala"
          />
        </FormRow>
        <FormRow label="Ekin" htmlFor="f-crop">
          <select id="f-crop" className="input" value={crop} onChange={(e) => setCrop(e.target.value)}>
            <option value="">— tanlanmagan —</option>
            {crops.map((c) => (
              <option key={c.key} value={c.key}>
                {c.name_uz} ({c.family_uz})
              </option>
            ))}
          </select>
        </FormRow>
        <FormRow label="Ekish sanasi" htmlFor="f-date">
          <input id="f-date" type="date" className="input" value={plantingDate} onChange={(e) => setPlantingDate(e.target.value)} />
        </FormRow>
        <FormRow label="Tuproq turi (mexanik tarkibi)" htmlFor="f-soil">
          <select id="f-soil" className="input" value={soil} onChange={(e) => setSoil(e.target.value)}>
            <option value="">— noma'lum —</option>
            {soils.map((s) => (
              <option key={s.key} value={s.key}>
                {s.name_uz}
              </option>
            ))}
          </select>
        </FormRow>
        <FormRow label="Mavjud suv, m³/ga (ixtiyoriy)" error={waterErr} hint="Mavsum davomida olinadigan suv limiti" htmlFor="f-water">
          <input id="f-water" className="input" inputMode="decimal" value={water} onChange={(e) => setWater(e.target.value)} placeholder="Masalan: 6000" />
        </FormRow>
        <FormRow label="Tuproq pH (laboratoriya)" error={phErr} hint="Ixtiyoriy, 3–10" htmlFor="f-ph">
          <input id="f-ph" className="input" inputMode="decimal" value={ph} onChange={(e) => setPh(e.target.value)} placeholder="Masalan: 7.2" />
        </FormRow>
        <FormRow label="Sho'rlanish ECe, dS/m (laboratoriya)" error={ecErr} hint="Ixtiyoriy, 0–30" htmlFor="f-ec">
          <input id="f-ec" className="input" inputMode="decimal" value={ec} onChange={(e) => setEc(e.target.value)} placeholder="Masalan: 2.5" />
        </FormRow>
      </Card>

      {saveError && <ErrorBox error={saveError} />}
      {!native && (
        <button type="button" className="btn btn--primary btn--block btn--lg" disabled={!canSave} onClick={save}>
          {saving ? 'Saqlanmoqda…' : 'Saqlash'}
        </button>
      )}
      {!canSave && !saving && (
        <div className="muted small center">
          {nameErr ? 'Dala nomini kiriting. ' : ''}
          {!geometryOk ? "Dala chegarasini to'g'ri belgilang." : ''}
        </div>
      )}
    </Page>
  )
}
