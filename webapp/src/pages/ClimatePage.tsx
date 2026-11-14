/** Iqlim siljishi — GET /fields/{id}/climate-shift (NASA POWER / MERRA-2, yearly). Handles 202 pending. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getClimateShift } from '../api/endpoints'
import type { ClimateShift, ClimateYear } from '../api/types'
import { AXIS_TICK_FONT, useChartTheme } from '../components/chartTheme'
import { Card, ErrorBox, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { fmtNum, fmtSigned } from '../utils/format'

const RETRY_SECONDS = 20

function YearChart({
  years,
  series,
  unit,
  kind,
}: {
  years: ClimateYear[]
  series: { key: keyof ClimateYear; name: string; color: number }[]
  unit: string
  kind: 'line' | 'bar'
}) {
  const theme = useChartTheme()
  const common = {
    data: years,
    margin: { top: 8, right: 8, left: 0, bottom: 0 },
  }
  const axes = (
    <>
      <CartesianGrid stroke={theme.grid} vertical={false} />
      <XAxis dataKey="year" tick={{ fontSize: AXIS_TICK_FONT, fill: theme.axis }} stroke={theme.grid} minTickGap={16} />
      {/* Bars need a zero baseline; lines show the trend, so let the axis fit the data. */}
      <YAxis
        width={44}
        tick={{ fontSize: AXIS_TICK_FONT, fill: theme.axis }}
        stroke={theme.grid}
        domain={kind === 'bar' ? [0, 'auto'] : ['auto', 'auto']}
        tickFormatter={(v) => fmtNum(v, 1)}
      />
      <Tooltip
        formatter={(v, name) => [`${fmtNum(v as number, 1)} ${unit}`, name]}
        contentStyle={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 8, color: theme.text }}
        labelStyle={{ color: theme.text }}
      />
      {series.length > 1 && (
        <Legend wrapperStyle={{ fontSize: AXIS_TICK_FONT }} formatter={(value) => <span style={{ color: theme.text }}>{value}</span>} />
      )}
    </>
  )
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        {kind === 'bar' ? (
          <BarChart {...common}>
            {axes}
            {series.map((s) => (
              <Bar key={String(s.key)} dataKey={s.key as string} name={s.name} fill={theme.series[s.color]} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            ))}
          </BarChart>
        ) : (
          <LineChart {...common}>
            {axes}
            {series.map((s) => (
              <Line
                key={String(s.key)}
                type="monotone"
                dataKey={s.key as string}
                name={s.name}
                stroke={theme.series[s.color]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat__value">{value}</div>
      <div className="stat__label">{label}</div>
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  )
}

function ClimateView({ data }: { data: ClimateShift }) {
  const t = data.trend
  const r = data.recent_vs_baseline
  return (
    <>
      <Card title="Xulosa">
        {data.summary_uz ? <p>{data.summary_uz}</p> : <p className="muted">Xulosa yo'q</p>}
        <div className="muted small">
          🛰 Manba: {data.source} · 📐 {data.resolution} · Bazaviy davr: {data.baseline_period}
        </div>
      </Card>

      <Card title={`So'nggi davr (${r.period}) bazaviy davrga (${data.baseline_period}) nisbatan`}>
        <div className="stat-grid">
          <Stat label="O'rtacha harorat" value={`${fmtSigned(r.t_mean_delta, 1)} °C`} />
          <Stat label="Yillik yog'in" value={`${fmtSigned(r.precip_delta_pct, 1)} %`} />
          <Stat label="Issiq kunlar" value={`${fmtSigned(r.hot_days_delta, 1)} kun/yil`} />
        </div>
      </Card>

      <Card title="Trend (har 10 yilda)">
        <div className="stat-grid">
          <Stat label="Harorat" value={`${fmtSigned(t.t_mean_per_decade, 2)} °C`} />
          <Stat label="Yog'in" value={`${fmtSigned(t.precip_per_decade, 1)} mm`} />
          <Stat label="Issiq kunlar" value={`${fmtSigned(t.hot_days_per_decade, 1)} kun`} />
          <Stat label="Sovuq kunlar" value={`${fmtSigned(t.frost_days_per_decade, 1)} kun`} />
        </div>
      </Card>

      <Card title="Yillik o'rtacha harorat, °C">
        <YearChart years={data.years} unit="°C" kind="line" series={[{ key: 't_mean', name: "O'rtacha harorat", color: 2 }]} />
      </Card>
      <Card title="Yillik yog'in, mm">
        <YearChart years={data.years} unit="mm" kind="bar" series={[{ key: 'precip_total', name: "Yog'in", color: 1 }]} />
      </Card>
      <Card title="Issiq va sovuq kunlar soni">
        <YearChart
          years={data.years}
          unit="kun"
          kind="line"
          series={[
            { key: 'hot_days', name: 'Issiq kunlar', color: 2 },
            { key: 'frost_days', name: 'Sovuq urgan kunlar', color: 1 },
          ]}
        />
      </Card>
    </>
  )
}

export function ClimatePage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const res = useAsync(() => getClimateShift(fieldId), [fieldId])
  const pending = res.data?.status === 'pending'
  const [countdown, setCountdown] = useState(RETRY_SECONDS)

  // While the backend is still fetching 40+ years of NASA POWER data, retry automatically.
  useEffect(() => {
    if (!pending) return
    setCountdown(RETRY_SECONDS)
    const timer = setInterval(() => setCountdown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(timer)
  }, [pending])

  const { reload } = res
  useEffect(() => {
    if (pending && countdown === 0) {
      setCountdown(RETRY_SECONDS)
      reload()
    }
  }, [pending, countdown, reload])

  return (
    <Page title="Iqlim siljishi" subtitle="NASA POWER, 1981-yildan buyon" back={`/fields/${fieldId}`}>
      {res.loading && !res.data && <Loading />}
      {res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
      {pending && (
        <Card title="Ma'lumot tayyorlanmoqda" tone="info">
          <p>NASA ma'lumotlari yuklanmoqda, keyinroq qayta urinib ko'ring.</p>
          <p className="muted small">Avtomatik qayta so'rash: {countdown} soniyadan keyin.</p>
          <button type="button" className="btn btn--secondary" onClick={res.reload} disabled={res.loading}>
            {res.loading ? 'Tekshirilmoqda…' : 'Hozir qayta urinish'}
          </button>
        </Card>
      )}
      {res.data?.status === 'ready' && <ClimateView data={res.data.data} />}
    </Page>
  )
}
