/** Qurilmalar — GET/POST/DELETE /devices. The device token is shown exactly once after creation. */
import { useState } from 'react'
import { createDevice, deleteDevice, getDevices, getFields } from '../api/endpoints'
import type { DeviceCreated } from '../api/types'
import { DeviceItem } from '../components/DeviceItem'
import { Card, Empty, ErrorBox, FormRow, Loading, Page } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { confirmDialog, haptic } from '../telegram'

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

function CopyBox({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState<boolean | null>(null)
  return (
    <div className="copy-box">
      <div className="copy-box__label">{label}</div>
      <div className="copy-box__row">
        <code className="copy-box__value">{value}</code>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={async () => {
            const ok = await copyText(value)
            setCopied(ok)
            if (ok) haptic('success')
          }}
        >
          {copied ? '✓ Nusxalandi' : 'Nusxalash'}
        </button>
      </div>
      {copied === false && <div className="muted small">Nusxalab bo'lmadi — matnni bosib turib qo'lda nusxalang.</div>}
    </div>
  )
}

function CreatedDevice({ created, onClose }: { created: DeviceCreated; onClose: () => void }) {
  const snippet = `#define DEVICE_ID    "${created.device.device_id}"\n#define DEVICE_TOKEN "${created.token}"`
  return (
    <Card title="Qurilma qo'shildi" tone="warning">
      <div className="warning-text">
        ⚠️ Token faqat hozir <strong>bir marta</strong> ko'rsatiladi. Uni nusxalab, xavfsiz joyda saqlang — keyin qayta ko'rsatilmaydi.
        Yo'qolsa, qurilmani o'chirib, yangisini qo'shing.
      </div>
      <CopyBox label="DEVICE_ID" value={created.device.device_id} />
      <CopyBox label="DEVICE_TOKEN" value={created.token} />
      <div className="steps">
        <div className="steps__title">ESP32 proshivkasini sozlash</div>
        <ol>
          <li>
            <code>firmware/esp32/include/config.h</code> faylini oching.
          </li>
          <li>
            <code>DEVICE_ID</code> va <code>DEVICE_TOKEN</code> qiymatlarini quyidagicha yozing:
          </li>
        </ol>
        <CopyBox label="config.h" value={snippet} />
        <ol start={3}>
          <li>Wi-Fi nomi/paroli va server manzilini ham shu faylda tekshiring.</li>
          <li>PlatformIO orqali yuklang (Upload) va qurilmani dalaga o'rnating.</li>
          <li>Birinchi o'lchov kelgach, holat "🟢 Onlayn" bo'ladi.</li>
        </ol>
      </div>
      <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
        Tokenni saqladim
      </button>
    </Card>
  )
}

export function DevicesPage() {
  const devices = useAsync(getDevices, [])
  const fields = useAsync(getFields, [])
  const [name, setName] = useState('')
  const [fieldId, setFieldId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<DeviceCreated | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)

  const fieldName = (id: number | null) => (id === null ? null : (fields.data?.find((f) => f.id === id)?.name ?? `#${id}`))

  const add = async () => {
    if (!name.trim() || !fieldId) return
    setBusy(true)
    setError(null)
    try {
      const res = await createDevice(name.trim(), Number(fieldId))
      setCreated(res)
      setName('')
      devices.setData((prev) => [...(prev ?? []), res.device])
      haptic('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number, devName: string) => {
    const ok = await confirmDialog(`"${devName}" qurilmasini o'chirasizmi? Uning tokeni bekor qilinadi.`)
    if (!ok) return
    setDeleting(id)
    try {
      await deleteDevice(id)
      devices.setData((prev) => (prev ?? []).filter((d) => d.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <Page title="Qurilmalar" subtitle="ESP32 sensorlarini dalaga bog'lash">
      {created && <CreatedDevice created={created} onClose={() => setCreated(null)} />}

      {devices.loading && !devices.data && <Loading />}
      {devices.error && <ErrorBox error={devices.error} onRetry={devices.reload} />}
      {devices.data && devices.data.length === 0 && <Empty>Hali qurilma qo'shilmagan</Empty>}
      {devices.data?.map((d) => (
        <DeviceItem
          key={d.id}
          device={d}
          fieldName={fieldName(d.field_id)}
          actions={
            <button type="button" className="btn btn--danger-ghost" disabled={deleting === d.id} onClick={() => remove(d.id, d.name)}>
              {deleting === d.id ? "O'chirilmoqda…" : "🗑 O'chirish"}
            </button>
          }
        />
      ))}

      <Card title="Qurilma qo'shish">
        <FormRow label="Qurilma nomi *" htmlFor="d-name">
          <input id="d-name" className="input" maxLength={60} placeholder="Masalan: Dala sensori 1" value={name} onChange={(e) => setName(e.target.value)} />
        </FormRow>
        <FormRow label="Dala *" htmlFor="d-field" hint={fields.data?.length === 0 ? "Avval dala qo'shing" : undefined}>
          <select id="d-field" className="input" value={fieldId} onChange={(e) => setFieldId(e.target.value)}>
            <option value="">— tanlang —</option>
            {(fields.data ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </FormRow>
        {error && <ErrorBox error={error} />}
        <button type="button" className="btn btn--primary btn--block" disabled={busy || !name.trim() || !fieldId} onClick={add}>
          {busy ? "Qo'shilmoqda…" : "Qurilma qo'shish"}
        </button>
      </Card>
    </Page>
  )
}
