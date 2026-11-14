/** Dala paneli — GET /fields/{id}/dashboard (TG-5, TG-6, DSS, FB). */
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { deleteField, getDashboard, getSoilTextures, runDemoScenario, type DemoScenario } from '../api/endpoints'
import type { CropStatus, Dashboard, Metric, MetricSource, NasaEvents, YieldForecast } from '../api/types'
import { DeviceItem } from '../components/DeviceItem'
import { IconCalendar, IconChart, IconChat, IconClipboard, IconRefresh, IconRotate, IconThermometer } from '../components/icons'
import { FieldMiniMap } from '../components/FieldMiniMap'
import { ForecastStrip } from '../components/ForecastStrip'
import { MetricCard } from '../components/MetricCard'
import { RecommendationCard } from '../components/RecommendationCard'
import { BulletList, Card, ConfidenceBadge, DemoBadge, Empty, ErrorBox, KeyValue, Loading, Meter, NoData, Page, RangeBar, SeverityBadge } from '../components/ui'
import { useAuth } from '../auth'
import { useAsync } from '../hooks/useAsync'
import { confirmDialog, haptic, openExternalLink } from '../telegram'
import { fmtNum } from '../utils/format'
import { formatDateOnly, formatDateTime, formatRelative, formatWhen, weekdayShort } from '../utils/time'

const GROUPS: { id: MetricSource; title: string; hint?: string; sources: MetricSource[] }[] = [
  { id: 'sensor', title: 'Dala sensori', hint: "Dalaning o'zidagi o'lchov (bitta nuqta)", sources: ['sensor'] },
  { id: 'forecast', title: "Bugungi ob-havo", sources: ['forecast'] },
  {
    id: 'nasa',
    title: 'NASA — hudud foni',
    hint: "NASA POWER ~50 km katak bo'yicha hudud qiymati, dalaning o'z qiymati emas. GWET (0–1) sensor namligi (%) bilan to'g'ridan-to'g'ri solishtirilmaydi.",
    sources: ['nasa'],
  },
  { id: 'model', title: "Model va fermer ma'lumotlari", sources: ['model', 'farmer'] },
]

const SENSOR_KEYS = new Set(['soil_moisture', 'soil_temp', 'air_temp', 'air_humidity', 'light', 'rain_detected'])

/** A metric without data has source=null — place it by its key so "ma'lumot yo'q" still shows in the right group. */
function sourceOf(m: Metric): MetricSource {
  if (m.source) return m.source
  if (SENSOR_KEYS.has(m.key)) return 'sensor'
  if (m.key.startsWith('nasa_')) return 'nasa'
  return 'forecast'
}

function MetricsSection({ metrics }: { metrics: Metric[] }) {
  if (!metrics.length) return <Empty>Ko'rsatkichlar hali yo'q</Empty>
  return (
    <>
      {GROUPS.map((g) => {
        const items = metrics.filter((m) => g.sources.includes(sourceOf(m)))
        if (!items.length) return null
        return (
          <Card key={g.id} title={g.title}>
            {g.hint && <p className="muted small">{g.hint}</p>}
            <div className="metric-grid">
              {items.map((m) => (
                <MetricCard key={m.key} metric={m} />
              ))}
            </div>
          </Card>
        )
      })}
    </>
  )
}

function CropStatusCard({ status }: { status: CropStatus | null }) {
  if (!status) {
    return (
      <Card title="Ekin holati">
        <NoData text="Ma'lumot yetarli emas — ekin va ekish sanasini kiriting" />
      </Card>
    )
  }
  const w = status.water
  const taw = w?.taw_mm ?? null
  const dep = w?.depletion_mm ?? null
  const raw = w?.raw_mm ?? null
  const stressed = dep !== null && raw !== null && dep > raw
  return (
    <Card title="Ekin holati">
      <KeyValue
        items={[
          { label: 'Ekin', value: status.crop_name_uz },
          { label: 'Rivojlanish bosqichi', value: status.stage_uz },
          { label: 'Ekilganiga', value: status.days_since_planting !== null ? `${status.days_since_planting} kun` : <NoData /> },
          { label: "Yig'ilgan issiqlik (GDD)", value: status.gdd !== null ? `${fmtNum(status.gdd, 0)} °C·kun` : <NoData /> },
        ]}
      />
      <div className="water">
        <div className="water__title">Ildiz zonasidagi suv tanqisligi</div>
        {taw !== null && dep !== null ? (
          <>
            <div className="water__bar">
              <Meter value={(dep / taw) * 100} tone={stressed ? 'danger' : dep > (raw ?? taw) * 0.7 ? 'warning' : 'success'} />
              {raw !== null && <div className="water__raw" style={{ left: `${Math.min(100, (raw / taw) * 100)}%` }} title="RAW chegarasi" />}
            </div>
            <div className="water__legend">
              <span>
                Kamayish: <strong>{fmtNum(dep, 1)} mm</strong>
              </span>
              <span>RAW (stress chegarasi): {fmtNum(raw, 1)} mm</span>
              <span>TAW (jami): {fmtNum(taw, 1)} mm</span>
              {w?.ks !== null && w?.ks !== undefined && (
                <span>
                  Ks = {fmtNum(w.ks, 2)} {w.ks < 1 ? '(suv stressi)' : "(stress yo'q)"}
                </span>
              )}
            </div>
          </>
        ) : (
          <NoData />
        )}
      </div>
      {status.summary_uz && <p>{status.summary_uz}</p>}
    </Card>
  )
}

function YieldCard({ forecast }: { forecast: YieldForecast | null }) {
  if (!forecast) {
    return (
      <Card title="Hosildorlik prognozi">
        <NoData text="Ma'lumot yetarli emas" />
      </Card>
    )
  }
  const scale = Math.max(forecast.max_t_ha * 1.15, 1)
  return (
    <Card title="Hosildorlik prognozi" action={<ConfidenceBadge value={forecast.confidence} />}>
      <div className="yield">
        <div className="yield__likely">
          {fmtNum(forecast.likely_t_ha, 1)} <span className="yield__unit">t/ga</span>
        </div>
        <div className="muted">
          oraliq: {fmtNum(forecast.min_t_ha, 1)} – {fmtNum(forecast.max_t_ha, 1)} t/ga
        </div>
        <RangeBar min={forecast.min_t_ha} likely={forecast.likely_t_ha} max={forecast.max_t_ha} scaleMax={scale} />
        <div className="yield__labels">
          <span>min {fmtNum(forecast.min_t_ha, 1)}</span>
          <span>ehtimoliy {fmtNum(forecast.likely_t_ha, 1)}</span>
          <span>max {fmtNum(forecast.max_t_ha, 1)}</span>
        </div>
      </div>
      {forecast.method_uz && <p className="muted small">Usul: {forecast.method_uz}</p>}
      <div className="rec__list-title">Taxminlar</div>
      <BulletList items={forecast.assumptions} empty="—" />
    </Card>
  )
}

function ScheduleCard({ items }: { items: Dashboard['schedule'] }) {
  return (
    <Card title="Sug'orish va ishlar jadvali">
      {!items.length && <div className="muted">Rejalashtirilgan ish yo'q</div>}
      <ul className="schedule">
        {items.map((s, i) => (
          <li key={`${s.date}-${i}`} className={`schedule__item schedule__item--${s.kind}`}>
            <div className="schedule__date">
              <strong>{formatDateOnly(s.date)}</strong>
              <span className="muted small">{weekdayShort(s.date)}</span>
            </div>
            <div className="schedule__body">
              <div>
                {s.kind === 'irrigation' ? '💧' : '🚜'} <strong>{s.title_uz}</strong>
              </div>
              {(s.amount_mm !== null || s.amount_m3_ha !== null) && (
                <div>
                  {s.amount_mm !== null && `${fmtNum(s.amount_mm, 0)} mm`}
                  {s.amount_mm !== null && s.amount_m3_ha !== null && ' = '}
                  {s.amount_m3_ha !== null && `${fmtNum(s.amount_m3_ha, 0)} m³/ga`}
                </div>
              )}
              {s.details_uz && <div className="muted small">{s.details_uz}</div>}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** NASA EONET natural events near the field (wildfires, storms, floods, …). */
function NasaEventsCard({ data }: { data: NasaEvents }) {
  return (
    <Card title={`🛰 NASA EONET — yaqin atrofdagi tabiiy hodisalar (~${fmtNum(data.radius_km, 0)} km)`} className="card--compact">
      {data.events.length === 0 ? (
        <div className="muted small">
          Hozircha faol tabiiy hodisa yo'q
          {data.checked_at ? ` · tekshirildi: ${formatRelative(data.checked_at)} (${formatDateTime(data.checked_at)})` : ''}
        </div>
      ) : (
        <ul className="eonet">
          {data.events.map((e) => (
            <li key={e.id} className="eonet__item">
              <div className="eonet__body">
                <div className="eonet__title">{e.title}</div>
                <div className="muted small">
                  {e.categories.join(', ') || 'Tabiiy hodisa'} · {formatWhen(e.date)}
                </div>
              </div>
              {e.link && (
                <button type="button" className="btn btn--chip" onClick={() => openExternalLink(e.link!)}>
                  Batafsil
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="muted small">Manba: {data.source}</div>
    </Card>
  )
}

const SCENARIOS: { id: DemoScenario; label: string }[] = [
  { id: 'drought', label: "Qurg'oqchilik" },
  { id: 'heavy_rain', label: "Kuchli yomg'ir" },
  { id: 'sensor_fault', label: 'Sensor nosozligi' },
  { id: 'normal', label: 'Normal holat' },
]

/** Demo-only: simulate sensor scenarios through POST /admin/demo/{scenario} and refresh the dashboard. */
function DemoScenariosCard({ fieldId, alertTitles, onDone }: { fieldId: number; alertTitles: Map<string, string>; onDone: () => void }) {
  const [busy, setBusy] = useState<DemoScenario | null>(null)
  const [result, setResult] = useState<{ label: string; alerts: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (sc: (typeof SCENARIOS)[number]) => {
    setBusy(sc.id)
    setError(null)
    setResult(null)
    try {
      const res = await runDemoScenario(sc.id, fieldId)
      setResult({ label: sc.label, alerts: res.alerts ?? [] })
      haptic('success')
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card title="⚡ Demo ssenariylari" className="card--demo">
      <p className="muted small">Sensor ma'lumotini simulyatsiya qiladi va tahlilni qayta ishga tushiradi (faqat demo).</p>
      <div className="chips">
        {SCENARIOS.map((sc) => (
          <button key={sc.id} type="button" className="btn btn--chip" disabled={busy !== null} onClick={() => run(sc)}>
            {busy === sc.id ? <span className="spinner spinner--sm" aria-label="Bajarilmoqda" /> : null}
            {sc.label}
          </button>
        ))}
      </div>
      {result && (
        <div className="demo-result" role="status">
          <strong>{result.label}</strong> qo'llandi.{' '}
          {result.alerts.length
            ? `Ogohlantirishlar: ${result.alerts.map((a) => alertTitles.get(a) ?? a).join('; ')}`
            : "Yangi ogohlantirish yo'q."}
        </div>
      )}
      {error && <div className="form-row__error">{error}</div>}
    </Card>
  )
}

export function DashboardPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const navigate = useNavigate()
  const { farmer } = useAuth()
  const dash = useAsync(() => getDashboard(fieldId), [fieldId])
  const soils = useAsync(getSoilTextures, [])
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const d = dash.data
  const f = d?.field

  const remove = async () => {
    if (!f) return
    const ok = await confirmDialog(`"${f.name}" dalasini o'chirasizmi? Barcha tarix ham o'chadi.`)
    if (!ok) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteField(f.id)
      haptic('success')
      navigate('/', { replace: true })
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e))
      setDeleting(false)
    }
  }

  const soilName = f?.soil_texture ? (soils.data?.find((s) => s.key === f.soil_texture)?.name_uz ?? f.soil_texture) : null

  return (
    <Page
      title={f?.name ?? 'Dala paneli'}
      subtitle={
        f ? (
          <>
            {f.crop_name_uz ?? 'Ekin tanlanmagan'} {f.is_demo && <DemoBadge />}
          </>
        ) : undefined
      }
      back="/"
      actions={
        <button type="button" className="icon-btn" onClick={dash.reload} aria-label="Yangilash" disabled={dash.loading}>
          <IconRefresh size={20} />
        </button>
      }
    >
      {dash.loading && !d && <Loading />}
      {dash.error && <ErrorBox error={dash.error} onRetry={dash.reload} />}
      {d && f && (
        <>
          <div className="muted small">
            Yangilangan: {formatRelative(d.generated_at)} · {formatDateTime(d.generated_at)}
          </div>

          {d.alerts_active.length > 0 && (
            <Card title="Faol ogohlantirishlar" className="card--alerts">
              <ul className="alerts">
                {d.alerts_active.map((a, i) => (
                  <li key={`${a.type}-${i}`}>
                    <SeverityBadge value={a.severity} /> {a.title_uz}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title="Yer maydoni">
            <FieldMiniMap field={f} />
            <KeyValue
              items={[
                { label: 'Maydon', value: <strong>{fmtNum(f.area_ha, 2)} ga</strong> },
                { label: 'Markaz koordinatasi', value: <span className="mono">{f.centroid.lat.toFixed(5)}, {f.centroid.lon.toFixed(5)}</span> },
                { label: 'Belgilash usuli', value: f.drawing_method === 'quad' ? '4 burchak' : 'Polygon' },
                { label: 'Ekish sanasi', value: f.planting_date ? formatDateOnly(f.planting_date, true) : <NoData /> },
                ...(soilName ? [{ label: 'Tuproq turi', value: soilName }] : []),
                ...(f.soil_ph != null ? [{ label: 'Tuproq pH (lab.)', value: `✍️ ${fmtNum(f.soil_ph, 1)}` }] : []),
                ...(f.soil_ec_ds_m != null ? [{ label: "Sho'rlanish ECe (lab.)", value: `✍️ ${fmtNum(f.soil_ec_ds_m, 1)} dS/m` }] : []),
                ...(f.water_available_m3_ha != null ? [{ label: 'Mavjud suv', value: `✍️ ${fmtNum(f.water_available_m3_ha, 0)} m³/ga` }] : []),
              ]}
            />
            <div className="btn-row">
              <Link className="btn btn--secondary" to={`/fields/${f.id}/edit`}>
                Chegarani tahrirlash
              </Link>
            </div>
          </Card>

          <MetricsSection metrics={d.metrics} />

          <CropStatusCard status={d.crop_status} />
          <YieldCard forecast={d.yield_forecast} />

          <Card title="7 kunlik prognoz">
            <ForecastStrip days={d.forecast_daily} />
          </Card>

          {d.nasa_events && <NasaEventsCard data={d.nasa_events} />}

          <section className="section">
            <h2 className="section__title">Tavsiyalar</h2>
            {!d.recommendations.length && <Empty>Hozircha yangi tavsiya yo'q</Empty>}
            {d.recommendations.map((r) => (
              <RecommendationCard key={r.id} rec={r} />
            ))}
          </section>

          <ScheduleCard items={d.schedule} />

          {d.assumptions && d.assumptions.length > 0 && (
            <Card title="Umumiy taxminlar">
              <BulletList items={d.assumptions} />
            </Card>
          )}

          <Card title="Dala qurilmalari" action={<Link to="/devices" className="link">Boshqarish</Link>}>
            {!d.devices.length && <div className="muted">Bu dalaga sensor ulanmagan</div>}
            {d.devices.map((dev) => (
              <DeviceItem key={dev.id} device={dev} />
            ))}
          </Card>

          <nav className="tiles" aria-label="Dala bo'limlari">
            {[
              { to: `/fields/${f.id}/history`, label: 'Tarix va grafiklar', Icon: IconChart },
              { to: `/fields/${f.id}/climate`, label: 'Iqlim siljishi', Icon: IconThermometer },
              { to: `/fields/${f.id}/rotation`, label: 'Almashlab ekish', Icon: IconRotate },
              { to: `/fields/${f.id}/seasons`, label: 'Mavsumlar va hosil', Icon: IconCalendar },
              { to: `/fields/${f.id}/events`, label: 'Ishlar jurnali', Icon: IconClipboard },
              { to: `/chat?field=${f.id}`, label: "AI agronomdan so'rash", Icon: IconChat },
            ].map(({ to, label, Icon }) => (
              <Link key={to} className="tile" to={to}>
                <span className="icon-circle">
                  <Icon size={20} />
                </span>
                <span className="tile__label">{label}</span>
              </Link>
            ))}
          </nav>

          {farmer.is_demo && (
            <DemoScenariosCard
              fieldId={f.id}
              alertTitles={new Map(d.alerts_active.map((a) => [a.type, a.title_uz]))}
              onDone={dash.reload}
            />
          )}

          {deleteError && <ErrorBox error={deleteError} />}
          <button type="button" className="btn btn--danger btn--block" onClick={remove} disabled={deleting}>
            {deleting ? "O'chirilmoqda…" : "Dalani o'chirish"}
          </button>
        </>
      )}
    </Page>
  )
}
