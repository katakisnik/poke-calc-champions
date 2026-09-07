import { Input } from '@/components/ui/input'

const STAT_LABELS: Record<string, string> = { hp: 'HP', atk: 'Atk', def: 'Def', spa: 'SpA', spd: 'SpD', spe: 'Spe' }
const STAT_ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']

export function SpSpreadEditor({
  sp,
  onChange,
  spMax,
  spBudget,
}: {
  sp: Record<string, number>
  onChange: (sp: Record<string, number>) => void
  spMax: number
  spBudget: number
}) {
  const total = STAT_ORDER.reduce((sum, stat) => sum + (sp[stat] ?? 0), 0)
  const overBudget = total > spBudget
  const pct = Math.min((total / spBudget) * 100, 100)

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-6 gap-1.5">
        {STAT_ORDER.map((stat) => (
          <div key={stat} className="flex flex-col items-center gap-1">
            <label className="text-[11px] text-muted-foreground">{STAT_LABELS[stat]}</label>
            <Input
              type="number"
              min={0}
              max={spMax}
              value={sp[stat] ?? 0}
              onChange={(e) => {
                const raw = Number(e.target.value)
                const clamped = Math.max(0, Math.min(spMax, Number.isNaN(raw) ? 0 : raw))
                onChange({ ...sp, [stat]: clamped })
              }}
              className="h-8 px-1 text-center text-sm"
            />
          </div>
        ))}
      </div>
      <div className="h-1.5 overflow-hidden rounded bg-black/10 dark:bg-white/10">
        <div
          className={`h-full transition-[width] duration-200 ${overBudget ? 'bg-destructive' : 'bg-primary'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className={`text-xs ${overBudget ? 'font-medium text-destructive' : 'text-muted-foreground'}`}>
        {overBudget
          ? `SP total ${total} exceeds the ${spBudget}-point budget by ${total - spBudget}.`
          : `${total}/${spBudget} SP used (${spBudget - total} remaining)`}
      </p>
    </div>
  )
}

export function spTotalOverBudget(sp: Record<string, number>, spBudget: number): boolean {
  return STAT_ORDER.reduce((sum, stat) => sum + (sp[stat] ?? 0), 0) > spBudget
}
