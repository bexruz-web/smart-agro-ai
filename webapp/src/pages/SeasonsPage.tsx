/** Mavsumlar va hosil — GET/POST /fields/{id}/seasons, PATCH /seasons/{id}/harvest (ROT-1, FB-1, HIST). */
import { useState } from 'react'
import { useParams } from 'react-router'
import { getCrops, getSeasons, recordHarvest, startSeason } from '../api/endpoints'
import type { Crop, HarvestQuality, Season } from '../api/types'
import { Badge, Card, Empty, ErrorBox, FormRow, KeyValue, Loading, NoData, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { haptic } from '../telegram'
import { fmtNum, fmtSigned } from '../utils/format'
import { parseCoordinate } from '../utils/geo'
import { formatDateOnly, todayTashkent } from '../utils/time'

const QUALITIES: HarvestQuality[] = ["a'lo", 'yaxshi', "o'rta", 'past']

function HarvestForm({ season, onDone }: { season: Season; onDone: (s: Season) => void }) {
  const [date, setDate] = useState(todayTashkent())
  const [yieldText, setYieldText] = useState('')
  const [quality, setQuality] = useState<HarvestQuality>('yaxshi')
  const [waterText, setWaterText] = useState('')
  const [fertilizers, setFertilizers] = useState('')
  const [problems, setProblems] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const y = parseCoordinate(yieldText)
  const water = waterText.trim() ? parseCoordinate(waterText) : null
  const yErr = yieldText && (y === null || y < 0 || y > 200) ? "Hosilni t/ga da kiriting (masalan 4.2)" : null
  const wErr = waterText.trim() && (water === null || water < 0) ? 'Suv miqdorini m³ da kiriting' : null
  const valid = !!date && y !== null && !yErr && !wErr

  const submit = async () => {
    if (!valid || y === null) return
    setBusy(true)
    setError(null)
    try {
      const s = await recordHarvest(season.id, {
        harvest_date: date,
        yield_t_ha: y,
        quality,
        water_used_m3: water,
        fertilizers: fertilizers.trim() || null,
        problems: problems.trim() || null,
      })
      haptic('success')
      onDone(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="subform">
      <FormRow label="Hosil yig'ilgan sana *" htmlFor={`h-date-${season.id}`}>
        <input id={`h-date-${season.id}`} type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
      </FormRow>
      <FormRow label="Hosildorlik, t/ga *" error={yErr} htmlFor={`h-y-${season.id}`}>
        <input id={`h-y-${season.id}`} className="input" inputMode="decimal" placeholder="Masalan: 4.2" value={yieldText} onChange={(e) => setYieldText(e.target.value)} />
      </FormRow>
      <FormRow label="Hosil sifati">
        <div className="chips">
          {QUALITIES.map((q) => (
            <button key={q} type="button" className={`btn btn--chip ${quality === q ? 'is-active' : ''}`} onClick={() => setQuality(q)}>
              {q}
            </button>
          ))}
        </div>
      </FormRow>
      <FormRow label="Sarflangan suv, m³ (ixtiyoriy)" error={wErr} htmlFor={`h-w-${season.id}`}>
        <input id={`h-w-${season.id}`} className="input" inputMode="decimal" placeholder="Masalan: 5200" value={waterText} onChange={(e) => setWaterText(e.target.value)} />
      </FormRow>
      <FormRow label="Ishlatilgan o'g'itlar" htmlFor={`h-f-${season.id}`}>
        <textarea id={`h-f-${season.id}`} className="input" rows={2} placeholder="Masalan: ammiakli selitra 200 kg/ga" value={fertilizers} onChange={(e) => setFertilizers(e.target.value)} />
      </FormRow>
      <FormRow label="Yuzaga kelgan muammolar" htmlFor={`h-p-${season.id}`}>
        <textarea id={`h-p-${season.id}`} className="input" rows={2} placeholder="Masalan: may oyida do'l, zararkunanda" value={problems} onChange={(e) => setProblems(e.target.value)} />
      </FormRow>
      {error && <ErrorBox error={error} />}
      <button type="button" className="btn btn--primary btn--block" disabled={!valid || busy} onClick={submit}>
        {busy ? 'Saqlanmoqda…' : 'Hosilni saqlash'}
      </button>
    </div>
  )
}

function PredictedVsActual({ s }: { s: Season }) {
  if (s.yield_t_ha === null && s.predicted_yield_t_ha === null) return null
  const diff = s.yield_t_ha !== null && s.predicted_yield_t_ha ? ((s.yield_t_ha - s.predicted_yield_t_ha) / s.predicted_yield_t_ha) * 100 : null
  return (
    <div className="compare">
      <div className="compare__item">
        <div className="compare__label">Prognoz</div>
        <div className="compare__value">{s.predicted_yield_t_ha !== null ? `${fmtNum(s.predicted_yield_t_ha, 1)} t/ga` : <NoData />}</div>
      </div>
      <div className="compare__item">
        <div className="compare__label">Haqiqiy</div>
        <div className="compare__value">{s.yield_t_ha !== null ? `${fmtNum(s.yield_t_ha, 1)} t/ga` : <NoData />}</div>
      </div>
      <div className="compare__item">
        <div className="compare__label">Farq</div>
        <div className="compare__value">{diff !== null ? `${fmtSigned(diff, 0)}%` : '—'}</div>
      </div>
    </div>
  )
}

function SeasonCard({ season, onUpdate }: { season: Season; onUpdate: (s: Season) => void }) {
  const [open, setOpen] = useState(false)
  const active = season.status === 'active'
  return (
    <Card
      title={`${season.crop_name_uz ?? season.crop}`}
      action={<Badge tone={active ? 'success' : 'neutral'}>{active ? '🌱 Faol' : "✅ Yig'ilgan"}</Badge>}
    >
      <KeyValue
        items={[
          { label: 'Ekilgan', value: season.planting_date ? formatDateOnly(season.planting_date, true) : <NoData /> },
          ...(season.harvest_date ? [{ label: "Yig'ilgan", value: formatDateOnly(season.harvest_date, true) }] : []),
          ...(season.quality ? [{ label: 'Sifat', value: season.quality }] : []),
          ...(season.water_used_m3 !== null ? [{ label: 'Sarflangan suv', value: `${fmtNum(season.water_used_m3, 0)} m³` }] : []),
          ...(season.fertilizers ? [{ label: "O'g'itlar", value: season.fertilizers }] : []),
          ...(season.problems ? [{ label: 'Muammolar', value: season.problems }] : []),
        ]}
      />
      <PredictedVsActual s={season} />
      {active &&
        (open ? (
          <HarvestForm
            season={season}
            onDone={(s) => {
              setOpen(false)
              onUpdate(s)
            }}
          />
        ) : (
          <button type="button" className="btn btn--secondary btn--block" onClick={() => setOpen(true)}>
            🌾 Hosilni kiritish
          </button>
        ))}
    </Card>
  )
}

function StartSeasonForm({ crops, fieldId, onCreated }: { crops: Crop[]; fieldId: number; onCreated: (s: Season) => void }) {
  const [crop, setCrop] = useState('')
  const [date, setDate] = useState(todayTashkent())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!crop || !date) return
    setBusy(true)
    setError(null)
    try {
      onCreated(await startSeason(fieldId, crop, date))
      setCrop('')
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Yangi mavsum boshlash">
      <FormRow label="Ekin *" htmlFor="s-crop">
        <select id="s-crop" className="input" value={crop} onChange={(e) => setCrop(e.target.value)}>
          <option value="">— tanlang —</option>
          {crops.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name_uz}
            </option>
          ))}
        </select>
      </FormRow>
      <FormRow label="Ekish sanasi *" htmlFor="s-date">
        <input id="s-date" type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
      </FormRow>
      {error && <ErrorBox error={error} />}
      <button type="button" className="btn btn--primary btn--block" disabled={!crop || !date || busy} onClick={submit}>
        {busy ? 'Saqlanmoqda…' : 'Mavsumni boshlash'}
      </button>
    </Card>
  )
}

export function SeasonsPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const seasons = useAsync(() => getSeasons(fieldId), [fieldId])
  const crops = useAsync(getCrops, [])

  const list = [...(seasons.data ?? [])].sort((a, b) => (b.planting_date ?? '').localeCompare(a.planting_date ?? ''))
  const replace = (s: Season) => seasons.setData((prev) => (prev ?? []).map((x) => (x.id === s.id ? s : x)))

  return (
    <Page title="Mavsumlar va hosil" back={`/fields/${fieldId}`}>
      {seasons.loading && !seasons.data && <Loading />}
      {seasons.error && <ErrorBox error={seasons.error} onRetry={seasons.reload} />}
      {seasons.data && !list.length && <Empty>Hali mavsum qayd etilmagan</Empty>}
      {list.map((s) => (
        <SeasonCard key={s.id} season={s} onUpdate={replace} />
      ))}
      <StartSeasonForm crops={crops.data ?? []} fieldId={fieldId} onCreated={(s) => seasons.setData((prev) => [s, ...(prev ?? [])])} />
    </Page>
  )
}
