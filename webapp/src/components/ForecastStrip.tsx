import type { ForecastDay } from '../api/types'
import { fmtNum, weatherCodeInfo } from '../utils/format'
import { formatDateOnly, weekdayShort } from '../utils/time'

/** 7-day forecast (Open-Meteo). Scrolls inside its own container — never the page. */
export function ForecastStrip({ days }: { days: ForecastDay[] }) {
  if (!days.length) return <div className="muted">Prognoz ma'lumoti yo'q</div>
  return (
    <div className="forecast" role="list">
      {days.slice(0, 7).map((d) => {
        const w = weatherCodeInfo(d.weather_code)
        return (
          <div className="forecast__day" role="listitem" key={d.date}>
            <div className="forecast__wd">{weekdayShort(d.date)}</div>
            <div className="forecast__date">{formatDateOnly(d.date)}</div>
            <div className="forecast__icon" title={w.text}>
              {w.icon}
            </div>
            <div className="forecast__temp">
              <strong>{fmtNum(d.t_max, 0)}°</strong> <span className="muted">{fmtNum(d.t_min, 0)}°</span>
            </div>
            <div className="forecast__row" title="Yog'in">
              💧 {fmtNum(d.precipitation_mm, 1)} mm
            </div>
            <div className="forecast__row" title="Yog'in ehtimoli">
              ☔ {fmtNum(d.precipitation_probability, 0)}%
            </div>
            {d.snowfall_cm !== null && d.snowfall_cm > 0 && <div className="forecast__row">❄️ {fmtNum(d.snowfall_cm, 1)} sm</div>}
            <div className="forecast__row" title="Shamol (maks.)">
              🌬 {fmtNum(d.wind_max_ms, 0)} m/s
            </div>
            <div className="forecast__row" title="Bug'lanish (ET₀)">
              ET₀ {fmtNum(d.et0_mm, 1)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
