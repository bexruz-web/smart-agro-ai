/**
 * Settings: (a) land plots — open / edit / add; (b) notification interval → PATCH /me notify_schedule;
 * (c) language UZB · RUS · ENG → PATCH /me language (the UI switches immediately).
 */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { getFields, patchMe } from '../api/endpoints'
import type { NotifySchedule } from '../api/types'
import { useAuth } from '../auth'
import { RiskChip } from '../components/field'
import { IconEdit, IconPlus } from '../components/icons'
import { Card, ErrorBox, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { LANGS, LANG_LABEL, getLang, setLang, toLang, useI18n, type Lang, type MessageKey } from '../i18n'
import { haptic } from '../telegram'
import { fmtNum } from '../utils/format'

const SCHEDULES: NotifySchedule[] = ['daily3', '2h', '4h', '8h', '10h', 'weekly', 'monthly']
const SCHEDULE_LABEL: Record<NotifySchedule, MessageKey> = {
  daily3: 'notify.daily3',
  '2h': 'notify.2h',
  '4h': 'notify.4h',
  '8h': 'notify.8h',
  '10h': 'notify.10h',
  weekly: 'notify.weekly',
  monthly: 'notify.monthly',
}

function FieldsSection() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const fields = useAsync(getFields, [])
  return (
    <Card title={t('settings.fields')}>
      {fields.loading && !fields.data && <Loading />}
      {fields.error && <ErrorBox error={fields.error} onRetry={fields.reload} />}
      {fields.data && fields.data.length === 0 && <div className="muted">{t('settings.noFields')}</div>}
      {fields.data && fields.data.length > 0 && (
        <ul className="plot-list">
          {fields.data.map((f) => (
            <li key={f.id} className="plot">
              <Link to={`/fields/${f.id}`} className="plot__main">
                <span className="plot__name">{f.name}</span>
                <span className="plot__meta">
                  {fmtNum(f.area_ha, 2)} {t('unit.ha')} · <RiskChip risk={f.status?.drying_risk} />
                </span>
              </Link>
              <button type="button" className="icon-btn" onClick={() => navigate(`/fields/${f.id}/edit`)} aria-label={`${t('fieldPage.edit')}: ${f.name}`} title={t('fieldPage.edit')}>
                <IconEdit size={20} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="btn btn--secondary btn--block" onClick={() => navigate('/fields/new')}>
        <IconPlus size={20} /> {t('settings.addField')}
      </button>
    </Card>
  )
}

function NotifySection() {
  const { t } = useI18n()
  const { farmer, setFarmer } = useAuth()
  const saved = (SCHEDULES as string[]).includes(farmer.notify_schedule ?? '') ? (farmer.notify_schedule as NotifySchedule) : 'daily3'
  const [value, setValue] = useState<NotifySchedule>(saved)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const choose = async (s: NotifySchedule) => {
    if (busy || s === value) return
    const prev = value
    setValue(s)
    setBusy(true)
    setError(null)
    setOk(false)
    try {
      setFarmer(await patchMe({ notify_schedule: s }))
      setOk(true)
      haptic('success')
    } catch (e) {
      setValue(prev)
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={t('settings.notify')} action={ok ? <span className="saved">✓ {t('common.saved')}</span> : busy ? <span className="spinner spinner--sm" /> : undefined}>
      <div className="radio-list" role="radiogroup" aria-label={t('settings.notify')}>
        {SCHEDULES.map((s) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={value === s}
            className={`radio ${value === s ? 'is-active' : ''}`}
            onClick={() => choose(s)}
            disabled={busy}
          >
            <span className="radio__dot" aria-hidden="true" />
            <span className="radio__label">{t(SCHEDULE_LABEL[s])}</span>
          </button>
        ))}
      </div>
      <p className="muted small">{t('settings.notifyHint')}</p>
      {error && <ErrorBox error={error} />}
    </Card>
  )
}

function LanguageSection() {
  const { t, lang } = useI18n()
  const { setFarmer } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const choose = async (l: Lang) => {
    if (busy || l === lang) return
    const prev = getLang()
    setLang(l) // the whole UI switches immediately
    setBusy(true)
    setError(null)
    try {
      const f = await patchMe({ language: l })
      // Keep the choice even if an older backend does not echo the language back.
      setFarmer(toLang(f.language) ? f : { ...f, language: l })
      haptic('success')
    } catch (e) {
      setLang(prev)
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={t('settings.language')}>
      <div className="segmented" role="radiogroup" aria-label={t('settings.language')}>
        {LANGS.map((l) => (
          <button
            key={l}
            type="button"
            role="radio"
            aria-checked={lang === l}
            className={`segmented__item ${lang === l ? 'is-active' : ''}`}
            onClick={() => choose(l)}
            disabled={busy}
          >
            {LANG_LABEL[l]}
          </button>
        ))}
      </div>
      {error && <ErrorBox error={error} />}
    </Card>
  )
}

export function SettingsPage() {
  const { t } = useI18n()
  return (
    <Page title={t('settings.title')}>
      <FieldsSection />
      <NotifySection />
      <LanguageSection />
    </Page>
  )
}
