import { hpBarColor } from '@/lib/statColors'

/**
 * The defender's HP bar after this hit, in-game style (green above
 * half, yellow above a fifth, red below) - the % number is the hero
 * stat, but a bar is what actually reads as "damage" at a glance the
 * way the real battle HUD's HP gauge does. `remainingLo`/`remainingHi`
 * are 100 - the damage roll range, so the lighter "ghost" fill is the
 * best-case remaining HP and the solid fill on top of it is the
 * worst-case (guaranteed) remaining HP - the gap between them is the
 * roll's uncertainty.
 */
export function RemainingHpBar({ remainingLo, remainingHi }: { remainingLo: number; remainingHi: number }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
      <div
        className="absolute inset-y-0 left-0 rounded-full bg-foreground/20 transition-[width] duration-300"
        style={{ width: `${remainingHi}%` }}
      />
      <div
        className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-300"
        style={{ width: `${remainingLo}%`, backgroundColor: hpBarColor(remainingLo) }}
      />
    </div>
  )
}
