/** Small presentational building blocks. Styling lives in styles/app.css (tokens in theme.css). */
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { useBackButton } from '../hooks/useTelegramButtons'
import { useI18n } from '../i18n'
import { IconBack } from './icons'

interface PageProps {
  title: ReactNode
  subtitle?: ReactNode
  /** Path to go back to (or true for history back). Uses Telegram BackButton when available. */
  back?: string | true
  actions?: ReactNode
  children: ReactNode
  className?: string
}

export function Page({ title, subtitle, back, actions, children, className }: PageProps) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const goBack = back === undefined ? null : () => (back === true ? navigate(-1) : navigate(back))
  const native = useBackButton(goBack)
  return (
    <div className={`page ${className ?? ''}`}>
      <header className="page__header">
        {goBack && !native && (
          <button type="button" className="icon-btn page__back" onClick={goBack} aria-label={t('common.back')}>
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

export function Card({ title, children, className, action }: { title?: ReactNode; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <section className={`card ${className ?? ''}`}>
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

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'demo'

export function Badge({ tone = 'neutral', children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  )
}

export function DemoBadge() {
  const { t } = useI18n()
  return (
    <Badge tone="demo" title={t('common.demoHint')}>
      {t('common.demo')}
    </Badge>
  )
}

export function Loading({ text }: { text?: string }) {
  const { t } = useI18n()
  return (
    <div className="state state--loading">
      <div className="spinner" />
      <div>{text ?? t('common.loading')}</div>
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const { t } = useI18n()
  return (
    <div className="state state--error" role="alert">
      <div>⚠️ {typeof error === 'string' ? error : error.message}</div>
      {onRetry && (
        <button type="button" className="btn btn--secondary" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state state--empty">{children}</div>
}

/** Choice chips (single select) — used for crop, soil, irrigation and water source. */
export function ChipGroup({
  items,
  value,
  onChange,
  label,
  id,
}: {
  items: { key: string; name: string }[]
  value: string | null
  onChange: (key: string) => void
  label: string
  id?: string
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={label} id={id}>
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          role="radio"
          aria-checked={value === it.key}
          className={`btn btn--chip ${value === it.key ? 'is-active' : ''}`}
          onClick={() => onChange(it.key)}
        >
          {value === it.key && <span aria-hidden="true">✓</span>}
          {it.name}
        </button>
      ))}
    </div>
  )
}
