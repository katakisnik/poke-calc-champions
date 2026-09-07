/**
 * Base-stat quality bands, ported verbatim from ui/app.py's
 * BASE_STAT_MAX/STAT_COLOR_BANDS - same thresholds, same colors, same
 * "against the series-wide 0-255 scale" reasoning (so bar length
 * reflects absolute quality, not just relative to this one Pokemon's
 * own other stats).
 */
export const BASE_STAT_MAX = 255

const STAT_COLOR_BANDS: readonly [number, string][] = [
  [30, '#ff4d4d'], // red - very poor
  [60, '#ff9f40'], // orange - poor
  [90, '#ffd700'], // yellow - average
  [120, '#9bd63c'], // yellow-green - good
  [150, '#3fd63f'], // green - great
  [180, '#2fd6c8'], // cyan - excellent
  [255, '#4d8dff'], // blue - exceptional
]

export function statColor(value: number): string {
  for (const [threshold, color] of STAT_COLOR_BANDS) {
    if (value < threshold) return color
  }
  return STAT_COLOR_BANDS[STAT_COLOR_BANDS.length - 1][1]
}

/**
 * The classic in-game HP bar thresholds (green above half, yellow
 * between a fifth and half, red below a fifth) - used for a defender's
 * REMAINING HP after a hit, not the stat-quality bands above.
 */
export function hpBarColor(remainingPct: number): string {
  if (remainingPct > 50) return '#3fd63f'
  if (remainingPct > 20) return '#ffd700'
  return '#ff4d4d'
}
