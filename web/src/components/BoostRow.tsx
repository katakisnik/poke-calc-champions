import { Slider } from '@/components/ui/slider'

const STAT_LABELS: Record<string, string> = { atk: 'Atk', def: 'Def', spa: 'SpA', spd: 'SpD', spe: 'Spe' }
const BOOSTABLE_STATS = ['atk', 'def', 'spa', 'spd', 'spe']

export function BoostRow({
  boosts,
  onChange,
}: {
  boosts: Record<string, number>
  onChange: (boosts: Record<string, number>) => void
}) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {BOOSTABLE_STATS.map((stat) => (
        <div key={stat} className="flex flex-col items-center gap-1">
          <label className="text-[11px] text-muted-foreground">
            {STAT_LABELS[stat]} {boosts[stat] > 0 ? `+${boosts[stat]}` : boosts[stat]}
          </label>
          <Slider
            min={-6}
            max={6}
            step={1}
            value={[boosts[stat] ?? 0]}
            onValueChange={([v]) => onChange({ ...boosts, [stat]: v })}
          />
        </div>
      ))}
    </div>
  )
}
