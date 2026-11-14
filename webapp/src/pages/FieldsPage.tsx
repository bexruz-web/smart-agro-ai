import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { getDashboard, getFields, patchMe } from '../api/endpoints'
import type { Field } from '../api/types'
import { useAuth } from '../auth'
import { IconChevron, IconDroplet, IconPin, IconPlus } from '../components/icons'
import { Badge, Card, DemoBadge, Empty, ErrorBox, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { getCurrentLocation, haptic } from '../telegram'
import { fmtNum } from '../utils/format'
import { daysBetween, formatDateOnly, todayTashkent } from '../utils/time'

/**
 * Short status line from the field dashboard: worst active alert (critical first)
 * plus the latest sensor soil moisture, if there is one.
 */
function FieldStatus({ fieldId }: { fieldId: number }) {
  const dash = useAsync(() => getDashboard(fieldId), [fieldId])
  if (dash.loading) return <span className="muted small">Holat yuklanmoqda…</span>
  if (dash.error || !dash.data) return null
  const alerts = dash.data.alerts_active
  const critical = alerts.filter((a) => a.severity === 'critical')
  const top = critical[0] ?? alerts.find((a) => a.severity === 'warning') ?? alerts[0]
  const moisture = dash.data.metrics.find((m) => m.key === 'soil_moisture' && m.value !== null)
  return (
    <>
      {top ? (
        <Badge tone={top.severity === 'critical' ? 'danger' : top.severity === 'warning' ? 'warning' : 'success'}>
          {top.severity === 'critical' ? '🔴' : top.severity === 'warning' ? '🟠' : '🟢'} {top.title_uz}
          {alerts.length > 1 ? ` (+${alerts.length - 1})` : ''}
        </Badge>
      ) : (
        <Badge tone="success">✅ Ogohlantirish yo'q</Badge>
      )}
      {moisture && typeof moisture.value === 'number' && (
        <Badge tone="neutral">
          <IconDroplet size={14} /> Namlik {fmtNum(moisture.value, 1)}
          {moisture.unit ? ` ${moisture.unit}` : ''}
        </Badge>
      )}
    </>
  )
}

function FieldCard({ field }: { field: Field }) {
  const days = field.planting_date ? daysBetween(field.planting_date, todayTashkent()) : null
  return (
    <Link to={`/fields/${field.id}`} className="list-card">
      <div className="list-card__main">
        <div className="list-card__title">
          {field.name} {field.is_demo && <DemoBadge />}
        </div>
        <div className="list-card__meta">
          <span>{fmtNum(field.area_ha, 2)} ga</span>
          <span>·</span>
          <span>{field.crop_name_uz ?? 'Ekin tanlanmagan'}</span>
          {field.planting_date && (
            <>
              <span>·</span>
              <span>
                ekilgan {formatDateOnly(field.planting_date)}
                {days !== null && days >= 0 ? ` (${days} kun)` : ''}
              </span>
            </>
          )}
        </div>
        <div className="list-card__status">
          <FieldStatus fieldId={field.id} />
        </div>
      </div>
      <span className="list-card__chevron">
        <IconChevron size={20} />
      </span>
    </Link>
  )
}

/** TG-3: one-time farm location request (LocationManager → geolocation → manual map pick). */
function FarmLocationPrompt() {
  const { setFarmer } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const detect = async () => {
    setBusy(true)
    setError(null)
    try {
      const fix = await getCurrentLocation()
      const farmer = await patchMe({ farm_location: { lat: fix.lat, lon: fix.lon } })
      setFarmer(farmer)
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Xo'jalik joylashuvini belgilang" tone="success">
      <p className="muted">Xarita shu joydan ochiladi, ob-havo va NASA ma'lumotlari hudud bo'yicha olinadi.</p>
      {error && <div className="form-row__error">{error}</div>}
      <div className="btn-row">
        <button type="button" className="btn btn--primary" disabled={busy} onClick={detect}>
          <IconPin size={18} /> {busy ? 'Aniqlanmoqda…' : 'Joylashuvni aniqlash'}
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => navigate('/location')}>
          Xaritada tanlash
        </button>
      </div>
    </Card>
  )
}

export function FieldsPage() {
  const { farmer } = useAuth()
  const navigate = useNavigate()
  const fields = useAsync(getFields, [])
  const name = farmer.first_name ? `Salom, ${farmer.first_name}!` : 'Salom!'

  return (
    <Page
      title="Dalalarim"
      subtitle={
        <>
          {name} {farmer.is_demo && <DemoBadge />}
        </>
      }
    >
      {!farmer.farm_location && <FarmLocationPrompt />}

      <button type="button" className="btn btn--primary btn--block btn--lg" onClick={() => navigate('/fields/new')}>
        <IconPlus size={20} /> Dala qo'shish
      </button>

      {fields.loading && !fields.data && <Loading />}
      {fields.error && <ErrorBox error={fields.error} onRetry={fields.reload} />}
      {fields.data && fields.data.length === 0 && (
        <Empty>
          Hali dala qo'shilmagan. <br />
          Xaritada 4 burchakni belgilang yoki dalangizni chizing.
        </Empty>
      )}
      {fields.data && fields.data.length > 0 && (
        <div className="list">
          {fields.data.map((f) => (
            <FieldCard key={f.id} field={f} />
          ))}
        </div>
      )}
    </Page>
  )
}
