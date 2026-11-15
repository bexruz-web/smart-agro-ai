/**
 * Add / edit field — one simple sequential form with exactly 8 inputs + Save:
 * 1 name · 2 crop (chips) · 3 area (ha) · 4 planting date · 5 soil (chips) · 6 irrigation (chips)
 * · 7 water source (chips) · 8 location (tap the map) · Saqlash (Telegram MainButton + on-page).
 * POST /fields or PATCH /fields/{id}.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router'
import { createField, getCrops, getField, getOptions, getSoilTextures, updateField } from '../api/endpoints'
import type { Field, RefItem } from '../api/types'
import { useAuth } from '../auth'
import { PolygonPicker } from '../components/PolygonPicker'
import { ChipGroup, ErrorBox, Loading, Page } from '../components/ui'
import { DEFAULT_CENTER, DEFAULT_ZOOM, REGION_ZOOM } from '../config'
import { useAsync } from '../hooks/useAsync'
import { useMainButton } from '../hooks/useTelegramButtons'
import { useI18n } from '../i18n'
import { haptic } from '../telegram'
import {
  EMPTY_FORM,
  FORM_ORDER,
  formFromField,
  validateFieldForm,
  type FieldFormErrors,
  type FieldFormKey,
  type FieldFormValues,
} from '../utils/fieldForm'
import { todayTashkent } from '../utils/time'

/** Show a search box above the crop chips only when the list is long. */
const CROP_SEARCH_FROM = 12

function Step({ n, label, htmlFor, error, hint, children, id }: { n: number; label: string; htmlFor?: string; error?: string; hint?: ReactNode; children: ReactNode; id: string }) {
  return (
    <section className={`step ${error ? 'step--error' : ''}`} id={id}>
      <div className="step__head">
        <span className="step__num" aria-hidden="true">
          {n}
        </span>
        {htmlFor ? (
          <label className="step__label" htmlFor={htmlFor}>
            {label}
          </label>
        ) : (
          <h2 className="step__label">{label}</h2>
        )}
      </div>
      {children}
      {hint && !error && <div className="step__hint">{hint}</div>}
      {error && (
        <div className="step__error" role="alert">
          {error}
        </div>
      )}
    </section>
  )
}

function RefChips({ items, value, onChange, label, loading }: { items: RefItem[] | undefined; value: string | null; onChange: (k: string) => void; label: string; loading: boolean }) {
  if (!items) return loading ? <div className="spinner spinner--sm" /> : null
  return <ChipGroup items={items} value={value} onChange={onChange} label={label} />
}


function FieldForm({ field }: { field: Field | null }) {
  const { t, lang } = useI18n()
  const { farmer } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState<FieldFormValues>(() => (field ? formFromField(field, lang) : EMPTY_FORM))
  const [errors, setErrors] = useState<FieldFormErrors>({})
  const [submitted, setSubmitted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [cropQuery, setCropQuery] = useState('')

  const crops = useAsync(() => getCrops(lang), [lang])
  const soils = useAsync(() => getSoilTextures(lang), [lang])
  const options = useAsync(() => getOptions(lang), [lang])
  const refError = crops.error || soils.error || options.error

  // After the first save attempt, re-validate on every change so messages disappear as they are fixed.
  useEffect(() => {
    if (submitted) setErrors(validateFieldForm(values, t, undefined, lang).errors)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values, submitted, lang])

  const set = <K extends FieldFormKey>(key: K, v: FieldFormValues[K]) => setValues((prev) => ({ ...prev, [key]: v }))

  const shownCrops = useMemo(() => {
    const list = crops.data ?? []
    const q = cropQuery.trim().toLowerCase()
    if (!q) return list
    return list.filter((c) => c.name.toLowerCase().includes(q) || c.key === values.crop)
  }, [crops.data, cropQuery, values.crop])

  const save = async () => {
    if (busy) return
    setSubmitted(true)
    setServerError(null)
    const { errors: errs, input } = validateFieldForm(values, t, undefined, lang)
    setErrors(errs)
    if (!input) {
      haptic('error')
      const first = FORM_ORDER.find((k) => errs[k])
      if (first) document.getElementById(`step-${first}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setBusy(true)
    try {
      if (field) await updateField(field.id, input)
      else await createField(input)
      haptic('success')
      if (!field) navigate('/', { replace: true })
      // Back to where "Tahrirlash" was pressed (field page or settings) — it reloads its data.
      else if (((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0) navigate(-1)
      else navigate(`/fields/${field.id}`, { replace: true })
    } catch (e) {
      setServerError(e instanceof Error ? e.message : String(e))
      haptic('error')
      setBusy(false)
    }
  }

  useMainButton(busy ? t('common.saving') : t('common.save'), save, { visible: true, enabled: !busy, progress: busy })

  const region = farmer.farm_location
  const fallbackCenter = region ? { center: region, zoom: REGION_ZOOM + 2 } : { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM }
  const hasErrors = Object.keys(errors).length > 0

  return (
    <form
      className="form"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        save()
      }}
    >
      {refError && <ErrorBox error={t('form.refError')} onRetry={() => [crops, soils, options].forEach((r) => r.error && r.reload())} />}

      <Step n={1} id="step-name" label={t('form.name')} htmlFor="ff-name" error={errors.name}>
        <input
          id="ff-name"
          className="input input--lg"
          type="text"
          autoComplete="off"
          maxLength={160}
          placeholder={t('form.namePh')}
          value={values.name}
          onChange={(e) => set('name', e.target.value)}
        />
      </Step>

      <Step n={2} id="step-crop" label={t('form.crop')} error={errors.crop}>
        {(crops.data?.length ?? 0) > CROP_SEARCH_FROM && (
          <input
            className="input"
            type="search"
            placeholder={t('form.cropSearch')}
            aria-label={t('form.cropSearch')}
            value={cropQuery}
            onChange={(e) => setCropQuery(e.target.value)}
          />
        )}
        <RefChips items={crops.data ? shownCrops : undefined} value={values.crop} onChange={(k) => set('crop', k)} label={t('form.crop')} loading={crops.loading} />
        {crops.data && shownCrops.length === 0 && <div className="muted small">{t('form.cropNone')}</div>}
      </Step>

      <Step n={3} id="step-area" label={t('form.area')} htmlFor="ff-area" error={errors.area}>
        <input
          id="ff-area"
          className="input input--lg input--num"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          placeholder={t('form.areaPh')}
          value={values.area}
          onChange={(e) => set('area', e.target.value)}
        />
      </Step>

      <Step n={4} id="step-plantingDate" label={t('form.plantingDate')} htmlFor="ff-date" error={errors.plantingDate}>
        <input
          id="ff-date"
          className="input input--lg"
          type="date"
          max={`${Number(todayTashkent().slice(0, 4)) + 1}-12-31`}
          value={values.plantingDate}
          onChange={(e) => set('plantingDate', e.target.value)}
        />
      </Step>

      <Step n={5} id="step-soil" label={t('form.soil')} error={errors.soil}>
        <RefChips items={soils.data} value={values.soil} onChange={(k) => set('soil', k)} label={t('form.soil')} loading={soils.loading} />
      </Step>

      <Step n={6} id="step-irrigation" label={t('form.irrigation')} error={errors.irrigation}>
        <RefChips items={options.data?.irrigation_types} value={values.irrigation} onChange={(k) => set('irrigation', k)} label={t('form.irrigation')} loading={options.loading} />
      </Step>

      <Step n={7} id="step-water" label={t('form.water')} error={errors.water}>
        <RefChips items={options.data?.water_sources} value={values.water} onChange={(k) => set('water', k)} label={t('form.water')} loading={options.loading} />
      </Step>

      <Step
        n={8}
        id="step-location"
        label={t('form.location')}
        error={errors.location}
      >
        <PolygonPicker
          pin={values.location}
          polygon={values.polygon}
          onPin={(p) => set('location', p)}
          onPolygon={(pts) => set('polygon', pts)}
          fallbackCenter={fallbackCenter}
        />
      </Step>

      {hasErrors && submitted && <div className="form__summary">{t('form.fixErrors')}</div>}
      {serverError && <ErrorBox error={serverError} />}

      <button type="submit" className="btn btn--primary btn--block btn--lg" disabled={busy}>
        {busy ? t('common.saving') : t('common.save')}
      </button>
    </form>
  )
}

/** Route element for /fields/new and /fields/:id/edit (keyed so the form resets between them). */
export function FieldFormPage() {
  const { id } = useParams()
  const fieldId = id ? Number(id) : null
  return <FieldFormScreen key={id ?? 'new'} fieldId={fieldId} />
}

function FieldFormScreen({ fieldId }: { fieldId: number | null }) {
  const { t } = useI18n()
  const field = useAsync(() => (fieldId ? getField(fieldId) : Promise.resolve(null)), [fieldId])
  return (
    <Page title={fieldId ? t('form.titleEdit') : t('form.titleNew')} back={fieldId ? true : undefined}>
      {field.loading && <Loading />}
      {field.error && <ErrorBox error={field.error} onRetry={field.reload} />}
      {!field.loading && !field.error && <FieldForm field={field.data ?? null} />}
    </Page>
  )
}
