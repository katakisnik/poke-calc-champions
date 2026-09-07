import { TYPE_ORDER } from './typeColors'

/** Same ordering as ui/app.py's move_options(): canonical type order, then name within a type. */
export function sortMovesByType<T extends { type: string; name: string }>(moves: T[]): T[] {
  return [...moves].sort((a, b) => {
    const ta = TYPE_ORDER.indexOf(a.type)
    const tb = TYPE_ORDER.indexOf(b.type)
    if (ta !== tb) return ta - tb
    return a.name.localeCompare(b.name)
  })
}

/**
 * Groups in canonical type order, same as before - unless `stabTypes` is
 * given (a Pokemon's own type(s)), in which case the group(s) matching
 * those types are pulled to the front (primary type before secondary),
 * ahead of the rest, which keep their original canonical order. Moves
 * within a group are unaffected either way.
 */
export function groupMovesByType<T extends { type: string; name: string }>(
  moves: T[],
  stabTypes: readonly string[] = [],
): [string, T[]][] {
  const sorted = sortMovesByType(moves)
  const groups: [string, T[]][] = []
  for (const move of sorted) {
    const last = groups[groups.length - 1]
    if (last && last[0] === move.type) {
      last[1].push(move)
    } else {
      groups.push([move.type, [move]])
    }
  }
  if (stabTypes.length === 0) return groups

  const stab: [string, T[]][] = []
  const rest: [string, T[]][] = []
  for (const group of groups) {
    ;(stabTypes.includes(group[0]) ? stab : rest).push(group)
  }
  stab.sort((a, b) => stabTypes.indexOf(a[0]) - stabTypes.indexOf(b[0]))
  return [...stab, ...rest]
}
