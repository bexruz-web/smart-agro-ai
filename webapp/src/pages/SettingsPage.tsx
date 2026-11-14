/** Sozlamalar — PATCH /me: report interval (NOTIF-1), quiet hours (NOTIF-4), consent (TG-2), farm location (TG-3). */
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { patchMe } from '../api/endpoints'
import type { FarmerPatch, ReportInterval } from '../api/types'
import { useAuth } from '../auth'
import { Card, DemoBadge, ErrorBox, FormRow, KeyValue, NoData, Page } from '../components/ui'
import { haptic } from '../telegram'
import { formatLatLon } from '../utils/geo'
import { formatDateTime } from '../utils/time'

const INTERVALS: ReportInterval[] = [1, 2, 4, 6, 12, 24]
const HOURS = Array.from({ length: 24 }, (_, h) => h)
const hh = (h: number) => `${String(h).padStart(2, '0')}:00`

export function SettingsPage() {
  const { farmer, setFarmer, mode } = useAuth()
  const navigate = useNavigate()
  const [interval, setReportInterval] = useState<ReportInterval>(farmer.report_interval_hours)
  const [quietOn, setQuietOn] = useState(farmer.quiet_hours_start !== null && farmer.quiet_hours_end !== null)
  const [qStart, setQStart] = useState(farmer.quiet_hours_start ?? 22)
  const [qEnd, setQEnd] = useState(farmer.quiet_hours_end ?? 6)
  const [consent, setConsent] = useState(!!farmer.consent_at)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const dirty =
    interval !== farmer.report_interval_hours ||
    (quietOn ? qStart : null) !== farmer.quiet_hours_start ||
    (quietOn ? qEnd : null) !== farmer.quiet_hours_end ||
    (consent && !farmer.consent_at)

  const save = async () => {
    setBusy(true)
    setError(null)
    setSaved(false)
    const patch: FarmerPatch = {
      report_interval_hours: interval,
      quiet_hours_start: quietOn ? qStart : null,
      quiet_hours_end: quietOn ? qEnd : null,
    }
    if (consent && !farmer.consent_at) patch.consent = true
    try {
      setFarmer(await patchMe(patch))
      setSaved(true)
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page title="Sozlamalar">
      <Card title="Profil">
        <KeyValue
          items={[
            { label: 'Ism', value: farmer.first_name ?? <NoData text="—" /> },
            ...(farmer.username ? [{ label: 'Telegram', value: `@${farmer.username}` }] : []),
            { label: 'Kirish usuli', value: mode === 'telegram' ? 'Telegram' : <>Demo <DemoBadge /></> },
          ]}
        />
      </Card>

      <Card title="Xo'jalik joylashuvi">
        <div>{farmer.farm_location ? <span className="mono">{formatLatLon(farmer.farm_location)}</span> : <NoData text="Belgilanmagan" />}</div>
        <button type="button" className="btn btn--secondary btn--block" onClick={() => navigate('/location')}>
          {farmer.farm_location ? 'Joylashuvni yangilash' : 'Joylashuvni belgilash'}
        </button>
      </Card>

      <Card title="Hisobot intervali">
        <p className="muted small">Har bir dala bo'yicha hisobot shu oraliqda yuboriladi. Kritik ogohlantirishlar darhol keladi.</p>
        <div className="chips" role="radiogroup" aria-label="Hisobot intervali">
          {INTERVALS.map((h) => (
            <button
              key={h}
              type="button"
              role="radio"
              aria-checked={interval === h}
              className={`btn btn--chip ${interval === h ? 'is-active' : ''}`}
              onClick={() => setReportInterval(h)}
            >
              {h} soat
            </button>
          ))}
        </div>
      </Card>

      <Card title="Sokin soatlar">
        <label className="switch">
          <input type="checkbox" checked={quietOn} onChange={(e) => setQuietOn(e.target.checked)} />
          <span>Sokin soatlarni yoqish</span>
        </label>
        {quietOn && (
          <div className="two-cols">
            <FormRow label="Boshlanishi" htmlFor="q-start">
              <select id="q-start" className="input" value={qStart} onChange={(e) => setQStart(Number(e.target.value))}>
                {HOURS.map((h) => (
                  <option key={h} value={h}>
                    {hh(h)}
                  </option>
                ))}
              </select>
            </FormRow>
            <FormRow label="Tugashi" htmlFor="q-end">
              <select id="q-end" className="input" value={qEnd} onChange={(e) => setQEnd(Number(e.target.value))}>
                {HOURS.map((h) => (
                  <option key={h} value={h}>
                    {hh(h)}
                  </option>
                ))}
              </select>
            </FormRow>
          </div>
        )}
        <p className="muted small">Toshkent vaqti bo'yicha. 🔴 Kritik ogohlantirishlar sokin soatlarda ham keladi.</p>
      </Card>

      <Card title="Ma'lumotlarni qayta ishlashga rozilik">
        {farmer.consent_at ? (
          <div>✅ Rozilik berilgan: {formatDateTime(farmer.consent_at)}</div>
        ) : (
          <label className="switch">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>
              Dalalarim, sensor va hosil ma'lumotlarim tavsiyalar tayyorlash uchun qayta ishlanishiga roziman.
            </span>
          </label>
        )}
      </Card>

      {error && <ErrorBox error={error} />}
      {saved && !dirty && <div className="muted center">✅ Saqlandi</div>}
      <button type="button" className="btn btn--primary btn--block btn--lg" disabled={busy || !dirty} onClick={save}>
        {busy ? 'Saqlanmoqda…' : 'Saqlash'}
      </button>
    </Page>
  )
}
