/** Small presentational building blocks. Styling lives in styles/app.css (tokens in theme.css). */
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'
import type { Confidence, MetricSource, Severity } from '../api/types'
import { useBackButton } from '../hooks/useTelegramButtons'
import { IconBack } from './icons'
import { CONFIDENCE_LABEL, SEVERITY_LABEL, SOURCE_ICON, SOURCE_NAME } from '../utils/format'

interface PageProps {
  title: string
  subtitle?: ReactNode
  /** Path to go back to (or true for history back). Uses Telegram BackButton when available. */
  back?: string | true
  actions?: ReactNode
  children: ReactNode
}

export function Page({ title, subtitle, back, actions, children }: PageProps) {
  const navigate = useNavigate()
  const goBack = back === undefined ? null : () => (back === true ? navigate(-1) : navigate(back))
  const native = useBackButton(goBack)
  return (
    <div className="page">
      <header className="page__header">
        {goBack && !native && (
          <button type="button" className="icon-btn page__back" onClick={goBack} aria-label="Orqaga">
            <IconBack />
          </button>
        )}
        <div className="page__titles">
          <h1 className="page__title">{title}</h1>
          {subtitle && <div className="page__subtitle">{subtitle}</div>}
        </div>
        {actions && <div className="page__actions">{actions}</div>}
      </header>
      <main className="page__body">{children}</main>
    </div>
  )
}

export function Card({ title, children, className, tone, action }: { title?: ReactNode; children: ReactNode; className?: string; tone?: 'danger' | 'warning' | 'info' | 'success'; action?: ReactNode }) {
  return (
    <section className={`card ${tone ? `card--${tone}` : ''} ${className ?? ''}`}>
      {(title || action) && (
        <div className="card__head">
          {title && <h2 className="card__title">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Badge({ tone = 'neutral', children, title }: { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'demo' | 'accent'; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  )
}

export function DemoBadge() {
  return (
    <Badge tone="demo" title="Demo ma'lumot — haqiqiy o'lchov emas">
      DEMO
    </Badge>
  )
}

export function SourceBadge({ source, label }: { source: MetricSource | null; label?: string | null }) {
  if (!source && !label) return null
  const fallback = source ? `${SOURCE_ICON[source]} ${SOURCE_NAME[source]}` : ''
  return (
    <Badge tone="info" title={source ? SOURCE_NAME[source] : undefined}>
      {label || fallback}
    </Badge>
  )
}

export function ConfidenceBadge({ value }: { value: Confidence }) {
  const tone = value === 'high' ? 'success' : value === 'medium' ? 'warning' : 'danger'
  return <Badge tone={tone}>{CONFIDENCE_LABEL[value]}</Badge>
}

export function SeverityBadge({ value }: { value: Severity }) {
  const tone = value === 'critical' ? 'danger' : value === 'warning' ? 'warning' : 'success'
  return <Badge tone={tone}>{SEVERITY_LABEL[value]}</Badge>
}

export function Loading({ text = 'Yuklanmoqda…' }: { text?: string }) {
  return (
    <div className="state state--loading">
      <div className="spinner" />
      <div>{text}</div>
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <div>⚠️ {typeof error === 'string' ? error : error.message}</div>
      {onRetry && (
        <button type="button" className="btn btn--secondary" onClick={onRetry}>
          Qayta urinish
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state state--empty">{children}</div>
}

export function NoData({ text = "ma'lumot yo'q" }: { text?: string }) {
  return <span className="no-data">{text}</span>
}

export function FormRow({ label, hint, error, children, htmlFor }: { label: string; hint?: ReactNode; error?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div className={`form-row ${error ? 'form-row--error' : ''}`}>
      <label className="form-row__label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && !error && <div className="form-row__hint">{hint}</div>}
      {error && <div className="form-row__error">{error}</div>}
    </div>
  )
}

/** Horizontal bar showing a min–likely–max range on a 0..scaleMax axis. */
export function RangeBar({ min, likely, max, scaleMax }: { min: number; likely: number; max: number; scaleMax: number }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / (scaleMax || 1)) * 100))}%`
  return (
    <div className="range-bar" aria-hidden="true">
      <div className="range-bar__span" style={{ left: pct(min), width: `calc(${pct(max)} - ${pct(min)})` }} />
      <div className="range-bar__likely" style={{ left: pct(likely) }} />
    </div>
  )
}

/** Simple 0..100% progress meter. */
export function Meter({ value, tone = 'accent' }: { value: number; tone?: 'accent' | 'warning' | 'danger' | 'success' }) {
  return (
    <div className="meter">
      <div className={`meter__fill meter__fill--${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function KeyValue({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="kv">
      {items.map((it) => (
        <div className="kv__row" key={it.label}>
          <dt>{it.label}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function BulletList({ items, empty }: { items: string[]; empty?: string }) {
  if (!items.length) return empty ? <div className="muted">{empty}</div> : null
  return (
    <ul className="bullets">
      {items.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  )
}

export function Segmented<T extends string | number>({ value, options, onChange, ariaLabel }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; ariaLabel?: string }) {
  return (
    <div className="segmented" role="tablist" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className={`segmented__item ${o.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
