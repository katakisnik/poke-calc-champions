import { useState } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { TypeBadge } from '@/components/TypeBadge'
import { groupMovesByType } from '@/lib/sortMoves'
import { typeColor } from '@/lib/typeColors'
import { typeIcon } from '@/lib/typeIcons'
import { cn } from '@/lib/utils'
import type { MoveOut } from '@/api/client'

/** Small circular type-colored icon chip - the same role as the round
 * type icon on every move button in the real battle HUD, sized to sit
 * to the left of a move's name in a dense list row. */
function MoveTypeIcon({ type }: { type: string }) {
  const Icon = typeIcon(type)
  return (
    <span
      className="flex size-5 shrink-0 items-center justify-center rounded-full text-white shadow-sm"
      style={{ backgroundColor: typeColor(type) }}
    >
      <Icon className="size-3" strokeWidth={2.5} />
    </span>
  )
}

/**
 * The headline fix from the migration plan: Streamlit's st.selectbox
 * could only ever show flat text, so the old move picker faked grouping
 * with literal "── Fire ──" text rows, prefixed each move with an emoji
 * standing in for a real type badge, and had to specifically handle a
 * header row being selected as a no-op (a plain selectbox can't disable
 * individual options). Here it's a real grouped, searchable combobox
 * with actual colored type badges - none of that is a workaround.
 */
export function MoveCombobox({
  moves,
  value,
  onChange,
  stabTypes = [],
}: {
  moves: MoveOut[]
  value: string | null
  onChange: (moveId: string | null) => void
  /** The attacker's own type(s) - moves matching them are grouped first (STAB). */
  stabTypes?: string[]
}) {
  const [open, setOpen] = useState(false)
  const selected = moves.find((m) => m.id === value)
  const groups = groupMovesByType(moves, stabTypes)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open} className="w-full justify-between font-normal">
          {selected ? (
            <span className="flex items-center gap-2 truncate">
              <TypeBadge type={selected.type} />
              <span className="truncate">{selected.name}</span>
            </span>
          ) : (
            <span className="text-muted-foreground">(none)</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <Command>
          <CommandInput placeholder="Search moves..." />
          <CommandList className="max-h-80">
            <CommandEmpty>No match.</CommandEmpty>
            <CommandItem
              value="(none)"
              onSelect={() => {
                onChange(null)
                setOpen(false)
              }}
            >
              <Check className={cn('mr-2 h-4 w-4', value === null ? 'opacity-100' : 'opacity-0')} />
              (none)
            </CommandItem>
            {groups.map(([type, groupMoves]) => (
              <CommandGroup key={type} heading={<TypeBadge type={type} className="my-1" />}>
                {groupMoves.map((move) => (
                  <CommandItem
                    key={move.id}
                    value={move.name}
                    onSelect={() => {
                      onChange(move.id)
                      setOpen(false)
                    }}
                    className="border-l-[3px] data-[selected=true]:brightness-95"
                    style={{ borderLeftColor: typeColor(move.type), backgroundColor: `${typeColor(move.type)}0f` }}
                  >
                    <Check className={cn('h-4 w-4', value === move.id ? 'opacity-100' : 'opacity-0')} />
                    <MoveTypeIcon type={move.type} />
                    <span className="flex-1 truncate font-medium">{move.name}</span>
                    <span
                      className="ml-2 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground"
                      style={{ backgroundColor: `${typeColor(move.type)}22` }}
                    >
                      {move.category === 'Status' ? 'Status' : `${move.base_power} BP`}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
