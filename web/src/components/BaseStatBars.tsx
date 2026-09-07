import { BASE_STAT_MAX, statColor } from '@/lib/statColors'

const STAT_LABELS: Record<string, string> = { hp: 'HP', atk: 'Atk', def: 'Def', spa: 'SpA', spd: 'SpD', spe: 'Spe' }
const STAT_ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']

/**
 * Colored base-stat bars against the series-wide 0-255 scale - ported
 * from ui/app.py's render_base_stats(), which built this exact same
 * visual out of raw HTML strings inside st.markdown. Here it's real
 * elements with a transition, no string-building.
 */
export function BaseStatBars({ baseStats }: { baseStats: Record<string, number> }) {
  return (
    <div className="flex flex-col gap-1">
      {STAT_ORDER.map((stat) => {
        const value = baseStats[stat]
        const pct = Math.min(value / BASE_STAT_MAX, 1) * 100
        return (
          <div key={stat} className="flex items-center gap-2">
            <span className="w-9 text-xs opacity-75">{STAT_LABELS[stat]}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded bg-black/10 dark:bg-white/10">
              <div
                className="h-full rounded transition-[width] duration-300"
                style={{ width: `${pct}%`, backgroundColor: statColor(value) }}
              />
            </div>
            <span className="w-7 text-right text-xs font-semibold">{value}</span>
          </div>
        )
      })}
    </div>
  )
}
