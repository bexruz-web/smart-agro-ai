import { useMemo } from 'react'
import { cssVar } from '../map/colors'
import { getAppliedTheme } from '../telegram'

/** Chart colours resolved from theme tokens (recharts needs concrete values for SVG attributes). */
export function useChartTheme() {
  const scheme = getAppliedTheme()
  return useMemo(
    () => ({
      series: [cssVar('--chart-1', '#2e8b47'), cssVar('--chart-2', '#2563a8'), cssVar('--chart-3', '#d97a00'), cssVar('--chart-4', '#8b5cf6')],
      bad: cssVar('--chart-bad', '#c62f25'),
      grid: cssVar('--chart-grid', '#e2e6df'),
      axis: cssVar('--chart-axis', '#7b8574'),
      surface: cssVar('--color-card', '#ffffff'),
      text: cssVar('--color-text', '#18211a'),
      border: cssVar('--color-border', '#dde2da'),
    }),
    // Re-read when the colour scheme flips.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scheme],
  )
}

export const AXIS_TICK_FONT = 12
