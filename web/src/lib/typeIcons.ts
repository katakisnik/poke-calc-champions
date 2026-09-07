import {
  Bug, Circle, Droplet, FlaskConical, Feather, Flame, Ghost, Gem,
  Leaf, Mountain, Moon, Orbit, Brain, Shield, Snowflake, Sparkles, Swords, Zap,
  type LucideIcon,
} from 'lucide-react'

/**
 * Small glyph per type, echoing the circular type icons on each move
 * button in the real Pokemon Champions battle HUD - lucide has no
 * literal "dragon" or "fighting fist" icon, so Orbit/Swords stand in as
 * the closest visual fits rather than leaving those two typeless.
 */
export const TYPE_ICONS: Record<string, LucideIcon> = {
  Normal: Circle,
  Fire: Flame,
  Water: Droplet,
  Electric: Zap,
  Grass: Leaf,
  Ice: Snowflake,
  Fighting: Swords,
  Poison: FlaskConical,
  Ground: Mountain,
  Flying: Feather,
  Psychic: Brain,
  Bug: Bug,
  Rock: Gem,
  Ghost: Ghost,
  Dragon: Orbit,
  Dark: Moon,
  Steel: Shield,
  Fairy: Sparkles,
}

export function typeIcon(type: string): LucideIcon {
  return TYPE_ICONS[type] ?? Circle
}
