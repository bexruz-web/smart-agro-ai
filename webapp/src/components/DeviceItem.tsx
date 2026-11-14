import type { ReactNode } from 'react'
import type { Device } from '../api/types'
import { fmtNum } from '../utils/format'
import { formatObserved } from '../utils/time'
import { Badge } from './ui'

const STATUS: Record<Device['status'], { label: string; tone: 'success' | 'warning' | 'neutral' }> = {
  online: { label: '🟢 Onlayn', tone: 'success' },
  offline: { label: '🟠 Oflayn', tone: 'warning' },
  never: { label: "⚪ Hali ulanmagan", tone: 'neutral' },
}

export function DeviceItem({ device, fieldName, actions }: { device: Device; fieldName?: string | null; actions?: ReactNode }) {
  const st = STATUS[device.status] ?? STATUS.never
  return (
    <div className="device">
      <div className="device__head">
        <div>
          <div className="device__name">{device.name}</div>
          <div className="muted small mono">{device.device_id}</div>
        </div>
        <Badge tone={st.tone}>{st.label}</Badge>
      </div>
      <div className="device__meta">
        {fieldName !== undefined && <span>🌾 {fieldName ?? 'Dalaga bog\'lanmagan'}</span>}
        <span>🕒 {device.last_seen_at ? formatObserved(device.last_seen_at) : "hali ma'lumot yubormagan"}</span>
        {device.rssi !== null && <span>📶 {device.rssi} dBm</span>}
        {device.battery_v !== null && <span>🔋 {fmtNum(device.battery_v, 2)} V</span>}
        {device.firmware && <span>Proshivka: {device.firmware}</span>}
      </div>
      {actions && <div className="device__actions">{actions}</div>}
    </div>
  )
}
