/**
 * The classic per-type colors, ported verbatim from ui/app.py's
 * TYPE_COLORS - same values, same canonical ordering (used for grouping
 * moves by type). Object key order is significant here.
 */
export const TYPE_COLORS: Record<string, string> = {
  Normal: '#A8A878',
  Fire: '#F08030',
  Water: '#6890F0',
  Electric: '#F8D030',
  Grass: '#78C850',
  Ice: '#98D8D8',
  Fighting: '#C03028',
  Poison: '#A040A0',
  Ground: '#E0C068',
  Flying: '#A890F0',
  Psychic: '#F85888',
  Bug: '#A8B820',
  Rock: '#B8A038',
  Ghost: '#705898',
  Dragon: '#7038F8',
  Dark: '#705848',
  Steel: '#B8B8D0',
  Fairy: '#EE99AC',
}

export const TYPE_ORDER: readonly string[] = Object.keys(TYPE_COLORS)

export function typeColor(type: string): string {
  return TYPE_COLORS[type] ?? '#777777'
}
