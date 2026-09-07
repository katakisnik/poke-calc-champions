import { KO_ORDINAL_LABELS, MOVE_FLAG_LABELS } from '@/lib/fieldInfo'
import type { KoChanceEntry, MoveOut } from '@/api/client'

/** The move-info summary line, ported from ui/app.py's render_move_info(). */
export function moveInfoParts(move: MoveOut): string[] {
  const parts: string[] = [move.category, move.base_power ? `${move.base_power} BP` : '– BP']
  if (move.priority) parts.push(`Priority ${move.priority > 0 ? '+' : ''}${move.priority}`)
  if (move.target === 'allAdjacent') parts.push('Hits all adjacent Pokemon')
  else if (move.target === 'allAdjacentFoes') parts.push('Hits both foes')
  for (const flag of Object.keys(move.flags)) {
    if (MOVE_FLAG_LABELS[flag]) parts.push(MOVE_FLAG_LABELS[flag])
  }
  if (move.multihit) {
    const [lo, hi] = move.multihit
    parts.push(lo === 2 && hi === 2 ? 'Hits twice' : `Hits ${lo}-${hi} times`)
  }
  if (move.drain) {
    const [num, den] = move.drain
    parts.push(`Drains ${num}/${den} of damage dealt`)
  }
  if (move.recoil) parts.push(`Recoil ${Math.round(move.recoil * 100)}% of damage dealt`)
  if (move.will_crit) parts.push('Always a critical hit')
  if (move.breaks_protect) parts.push('Bypasses Protect')
  if (move.has_secondary) parts.push('Has a secondary effect')
  return parts
}

export interface KoChanceDisplayEntry {
  hits: number
  text: string
  isFinal: boolean // ~100% - the one to bold
}

/** Formats each KO-chance entry for display, ported from ui/app.py's
 * render_ko_chance() - only the LAST entry can ever be the ~100% one
 * (the backend's ko_chance() stops computing further hits once reached),
 * so bolding whichever hits that threshold needs no extra bookkeeping. */
export function formatKoChances(chances: KoChanceEntry[]): KoChanceDisplayEntry[] {
  const lastHits = Math.max(...chances.map((k) => k.hits))
  return chances.map(({ hits, probability }) => {
    const label = KO_ORDINAL_LABELS[hits] ?? `${hits}-hit KO`
    const suffix = hits === lastHits && probability < 0.9999 ? '+' : ''
    return {
      hits,
      text: `${label}${suffix} ${Math.round(probability * 100)}%`,
      isFinal: probability >= 0.9999,
    }
  })
}
