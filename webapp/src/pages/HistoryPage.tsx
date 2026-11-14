/** Tarix va grafiklar — GET /fields/{id}/timeseries (sensor + NASA POWER metrics). */
import { useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getTimeseries } from '../api/endpoints'
import type { Timeseries } from '../api/types'
import { AXIS_TICK_FONT, useChartTheme } from '../components/chartTheme'
import { Card, Empty, ErrorBox, FormRow, KeyValue, Loading, Page, Segmented, SourceBadge } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { fmtNum, QUALITY_LABEL } from '../utils/format'
import { formatDateTime, formatWhen, isoDaysAgo, tashkentParts } from '../utils/time'

const SENSOR_METRICS = [
  { key: 'soil_moisture', label: 'Tuproq namligi (%)' },
  { key: 'soil_temp', label: 'Tuproq harorati (°C)' },
  { key: 'air_temp', label: 'Havo harorati (°C)' },
  { key: 'air_humidity', label: 'Havo namligi (%)' },
  { key: 'light', label: 'Yorug\'lik (lux)' },
]
const NASA_METRICS = [
  { key: 'nasa_t2m', label: "O'rtacha harorat (T2M)" },
  { key: 'nasa_t2m_max', label: 'Maksimal harorat (T2M_MAX)' },
  { key: 'nasa_t2m_min', label: 'Minimal harorat (T2M_MIN)' },
  { key: 'nasa_precip', label: "Yog'in (PRECTOTCORR)" },
  { key: 'nasa_solar', label: 'Quyosh radiatsiyasi (ALLSKY_SFC_SW_DWN)' },
  { key: 'nasa_rh', label: 'Nisbiy namlik (RH2M)' },
  { key: 'nasa_gwettop', label: 'Ustki qatlam namligi (GWETTOP, 0–1)' },
  { key: 'nasa_gwetroot', label: 'Ildiz zonasi namligi (GWETROOT, 0–1)' },
]
const BAR_METRICS = new Set(['nasa_precip'])

const pad = (n: number) => String(n).padStart(2, '0')
function shortDate(ms: number): string {
  const p = tashkentParts(new Date(ms))
  return p ? `${pad(p.day)}.${pad(p.month)}` : ''
}
function shortTime(ms: number): string {
  const p = tashkentParts(new Date(ms))
  return p ? `${pad(p.hour)}:${pad(p.minute)}` : ''
}

interface Row {
  t: number
  v: number | null
  quality: string | null
  /** Display time: Tashkent date-time, or just the date for daily NASA values. */
  when: string
}

function stats(rows: Row[]) {
  const vals = rows.map((r) => r.v).filter((v): v is number => v !== null && Number.isFinite(v))
  if (!vals.length) return null
  const sum = vals.reduce((a, b) => a + b, 0)
  return { n: vals.length, min: Math.min(...vals), max: Math.max(...vals), avg: sum / vals.length, last: vals[vals.length - 1] }
}

function TimeseriesChart({ data }: { data: Timeseries }) {
  const theme = useChartTheme()
  const rows: Row[] = useMemo(
    () =>
      data.points
        .map((p) => ({ t: new Date(p.t).getTime(), v: p.v, quality: p.quality, when: formatWhen(p.t) }))
        .filter((r) => Number.isFinite(r.t))
        .sort((a, b) => a.t - b.t),
    [data.points],
  )
  const s = stats(rows)
  const whenByT = useMemo(() => new Map(rows.map((r) => [r.t, r.when])), [rows])
  // Short spans (e.g. a few hours of sensor data) get clock-time ticks instead of repeated dates.
  const spanMs = rows.length > 1 ? rows[rows.length - 1].t - rows[0].t : 0
  const unit = data.unit ?? ''
  const isBar = BAR_METRICS.has(data.metric)
  const flagged = rows.filter((r) => r.quality === 'suspect' || r.quality === 'bad').length

  if (!rows.length || !s) return <Empty>Bu davr uchun ma'lumot yo'q</Empty>

  const tooltip = (
    <Tooltip
      labelFormatter={(l) => whenByT.get(Number(l)) ?? formatDateTime(new Date(Number(l)))}
      formatter={(v, _n, item) => {
        const q = (item?.payload as Row | undefined)?.quality
        const qText = q && q !== 'ok' ? ` (${QUALITY_LABEL[q as 'suspect' | 'bad'] ?? q})` : ''
        return [`${fmtNum(v as number, 2)} ${unit}${qText}`, data.label_uz]
      }}
      contentStyle={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 8, color: theme.text }}
      labelStyle={{ color: theme.text }}
    />
  )
  const xAxis = (
    <XAxis
      dataKey="t"
      type="number"
      scale="time"
      domain={['dataMin', 'dataMax']}
      tickFormatter={spanMs < 2 * 86400000 ? shortTime : shortDate}
      tick={{ fontSize: AXIS_TICK_FONT, fill: theme.axis }}
      stroke={theme.grid}
      minTickGap={24}
    />
  )
  // Bars keep a zero baseline; lines fit the data range so changes stay visible.
  const yAxis = (
    <YAxis
      width={44}
      tick={{ fontSize: AXIS_TICK_FONT, fill: theme.axis }}
      stroke={theme.grid}
      domain={isBar ? [0, 'auto'] : ['auto', 'auto']}
      tickFormatter={(v) => fmtNum(v, 1)}
    />
  )

  return (
    <>
      <div className="chart" role="img" aria-label={`${data.label_uz} grafigi`}>
        <ResponsiveContainer width="100%" height={240}>
          {isBar ? (
            <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              {xAxis}
              {yAxis}
              {tooltip}
              <Bar dataKey="v" fill={theme.series[1]} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          ) : (
            <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              {xAxis}
              {yAxis}
              {tooltip}
              <Line
                type="monotone"
                dataKey="v"
                stroke={theme.series[0]}
                strokeWidth={2}
                connectNulls={false}
                isAnimationActive={false}
                dot={(props: { cx?: number; cy?: number; payload?: Row; index?: number }) => {
                  const q = props.payload?.quality
                  if ((q !== 'suspect' && q !== 'bad') || props.cx === undefined || props.cy === undefined)
                    return <g key={`d-${props.index}`} />
                  return <circle key={`d-${props.index}`} cx={props.cx} cy={props.cy} r={4} fill={theme.bad} stroke={theme.surface} strokeWidth={2} />
                }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      {flagged > 0 && <div className="muted small">⚠️ Qizil nuqtalar — sifati shubhali yoki yaroqsiz o'lchovlar ({flagged} ta).</div>}
      <KeyValue
        items={[
          { label: "So'nggi qiymat", value: `${fmtNum(s.last, 2)} ${unit}` },
          { label: "O'rtacha", value: `${fmtNum(s.avg, 2)} ${unit}` },
          { label: 'Minimum / maksimum', value: `${fmtNum(s.min, 2)} / ${fmtNum(s.max, 2)} ${unit}` },
          { label: "O'lchovlar soni", value: String(s.n) },
        ]}
      />
      <details className="table-view">
        <summary>Jadval ko'rinishi</summary>
        <table className="table">
          <thead>
            <tr>
              <th>Vaqt (Toshkent)</th>
              <th>Qiymat</th>
              <th>Sifat</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .slice(-100)
              .reverse()
              .map((r) => (
                <tr key={r.t}>
                  <td>{r.when}</td>
                  <td>{r.v === null ? "ma'lumot yo'q" : `${fmtNum(r.v, 2)} ${unit}`}</td>
                  <td>{r.quality ? (QUALITY_LABEL[r.quality as 'ok'] ?? r.quality) : '—'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </>
  )
}

export function HistoryPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const [metric, setMetric] = useState('soil_moisture')
  const [days, setDays] = useState<7 | 30 | 90>(30)
  const ts = useAsync(() => getTimeseries(fieldId, metric, isoDaysAgo(days), new Date().toISOString()), [fieldId, metric, days])
  const isNasa = metric.startsWith('nasa_')

  return (
    <Page title="Tarix va grafiklar" back={`/fields/${fieldId}`}>
      <Card>
        <FormRow label="Ko'rsatkich" htmlFor="h-metric">
          <select id="h-metric" className="input" value={metric} onChange={(e) => setMetric(e.target.value)}>
            <optgroup label="📡 Dala sensori">
              {SENSOR_METRICS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="🛰 NASA POWER (kunlik, hudud foni)">
              {NASA_METRICS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </optgroup>
          </select>
        </FormRow>
        <Segmented
          ariaLabel="Davr"
          value={days}
          onChange={setDays}
          options={[
            { value: 7, label: '7 kun' },
            { value: 30, label: '30 kun' },
            { value: 90, label: '90 kun' },
          ]}
        />
      </Card>

      {isNasa && (
        <div className="note">
          🛰 NASA POWER — ~50 km grid katagi bo'yicha <strong>hudud foni</strong>, dalaning o'z qiymati emas. Ma'lumot bir necha kun
          kechikadi (bugungi kun yo'q).
          {(metric === 'nasa_gwettop' || metric === 'nasa_gwetroot') &&
            ' GWET — MERRA-2 modelidagi g\'ovaklarning suv bilan to\'lganlik ulushi (0–1); sensor namligi (%) bilan to\'g\'ridan-to\'g\'ri solishtirilmaydi, faqat trend taqqoslanadi.'}
        </div>
      )}

      <Card
        title={ts.data?.label_uz ?? 'Grafik'}
        action={ts.data ? <SourceBadge source={ts.data.source} /> : undefined}
      >
        {ts.loading && <Loading />}
        {ts.error && <ErrorBox error={ts.error} onRetry={ts.reload} />}
        {!ts.loading && ts.data && <TimeseriesChart data={ts.data} />}
      </Card>
    </Page>
  )
}
