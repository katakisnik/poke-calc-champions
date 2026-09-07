import { typeColor } from '@/lib/typeColors'
import { typeIcon } from '@/lib/typeIcons'

/**
 * A real colored type badge - the thing a plain st.selectbox in the
 * Streamlit version could never render inside a dropdown (only flat
 * text), which is why the move picker there fell back to a `── Fire ──`
 * text header plus an emoji prefix. Here it's just... an element.
 *
 * The icon glyph echoes the small circular type icon on every move
 * button in the real Pokemon Champions battle HUD - a flat color chip
 * alone reads as a label, the icon is what makes it read as a badge.
 */
export function TypeBadge({ type, className = '' }: { type: string; className?: string }) {
  const Icon = typeIcon(type)
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white shadow-sm ${className}`}
      style={{ backgroundColor: typeColor(type), textShadow: '0 1px 1px rgba(0,0,0,0.35)' }}
    >
      <Icon className="size-3" strokeWidth={2.5} />
      {type}
    </span>
  )
}
