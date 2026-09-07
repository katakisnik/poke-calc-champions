import { useMemo } from 'react'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Combobox, type ComboboxOption } from '@/components/Combobox'
import { SpriteFrame } from '@/components/SpriteFrame'
import { TypeBadge } from '@/components/TypeBadge'
import { BaseStatBars } from '@/components/BaseStatBars'
import { SpSpreadEditor } from '@/components/SpSpreadEditor'
import { BoostRow } from '@/components/BoostRow'
import { TeamManager } from '@/components/TeamManager'
import { isItemLegal, useCalcStore, type Side } from '@/store/useCalcStore'
import { typeColor } from '@/lib/typeColors'

const STATUS_OPTIONS = [
  { value: '', label: '(none)' },
  { value: 'brn', label: 'Burn' },
  { value: 'par', label: 'Paralysis' },
  { value: 'psn', label: 'Poison' },
  { value: 'tox', label: 'Badly Poisoned' },
  { value: 'slp', label: 'Sleep' },
  { value: 'frz', label: 'Freeze' },
]

export function MonPanel({ side, label }: { side: Side; label: string }) {
  const bootstrap = useCalcStore((s) => s.bootstrap)
  const regulation = useCalcStore((s) => s.regulation)
  const build = useCalcStore((s) => s[side])
  const setMon = useCalcStore((s) => s.setMon)
  const selectSpecies = useCalcStore((s) => s.selectSpecies)

  const species = useMemo(() => bootstrap?.species.find((sp) => sp.id === build.species), [bootstrap, build.species])

  const speciesOptions: ComboboxOption[] = useMemo(
    () => (bootstrap?.species ?? []).map((sp) => ({ value: sp.id, label: sp.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [bootstrap],
  )

  const abilityOptions: ComboboxOption[] = useMemo(() => {
    if (!species || !bootstrap) return []
    return species.ability_slots
      .map((name) => bootstrap.abilities.find((a) => a.name === name))
      .filter((a): a is NonNullable<typeof a> => !!a)
      .map((a) => ({ value: a.name, label: a.name }))
  }, [species, bootstrap])

  const itemOptions: ComboboxOption[] = useMemo(() => {
    if (!bootstrap) return []
    return bootstrap.items
      .filter((i) => regulation === 'M-B' || i.legal_in_reg_m_a)
      .map((i) => ({ value: i.id, label: i.name }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [bootstrap, regulation])

  const natureOptions: ComboboxOption[] = useMemo(() => {
    if (!bootstrap) return []
    return bootstrap.natures.map((n) => ({
      value: n.name,
      label: n.name,
      render: (
        <span className="flex w-full items-center justify-between gap-2">
          <span>{n.name}</span>
          <span className="text-xs text-muted-foreground">
            {n.is_neutral ? 'Neutral' : `+${n.plus} / -${n.minus}`}
          </span>
        </span>
      ),
    }))
  }, [bootstrap])

  const ability = bootstrap?.abilities.find((a) => a.name === build.ability)
  const nature = bootstrap?.natures.find((n) => n.name === build.nature)
  const megaStoneItem = species?.mega_stone ? bootstrap?.items.find((i) => i.name === species.mega_stone) : undefined
  const itemLegal = isItemLegal(build.item, regulation, bootstrap)

  if (!bootstrap || !species) return null

  const edgeColor = typeColor(species.types[0])

  return (
    <Card
      className="pc-edge gap-2 py-2.5 transition-shadow duration-200 hover:shadow-md"
      style={{ '--pc-edge-color': `linear-gradient(90deg, ${edgeColor}, ${edgeColor}99)` } as React.CSSProperties}
    >
      <CardHeader>
        <CardTitle className="font-display text-lg">{label}</CardTitle>
        <CardAction>
          <TeamManager side={side} label={label} />
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex gap-3">
          <SpriteFrame url={species.sprite_url} />
          <div className="flex-1 space-y-2">
            <Combobox options={speciesOptions} value={species.id} onChange={(id) => selectSpecies(side, id)} placeholder="Species" />
            <div className="flex gap-1.5">
              {species.types.map((t) => (
                <TypeBadge key={t} type={t} />
              ))}
            </div>
          </div>
        </div>

        <BaseStatBars baseStats={species.base_stats} />

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Nature</label>
            <Combobox options={natureOptions} value={build.nature} onChange={(v) => setMon(side, { nature: v })} />
            {nature && (
              <p className="text-xs text-muted-foreground">
                {nature.is_neutral ? 'Neutral - no stat boost/cut' : `+${nature.plus} / -${nature.minus}`}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Ability</label>
            <Combobox options={abilityOptions} value={build.ability} onChange={(v) => setMon(side, { ability: v })} />
            {ability?.description && <p className="text-xs text-muted-foreground">{ability.description}</p>}
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Item</label>
            {megaStoneItem ? (
              <Combobox options={[{ value: megaStoneItem.id, label: megaStoneItem.name }]} value={megaStoneItem.id} onChange={() => {}} disabled />
            ) : (
              <Combobox options={itemOptions} value={build.item} onChange={(v) => setMon(side, { item: v })} placeholder="(none)" />
            )}
            {megaStoneItem && !itemLegal && (
              <p className="text-xs font-medium text-destructive">
                {megaStoneItem.name} isn't legal under Regulation {regulation} - this Mega can't be used here.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Status</label>
            <Select value={build.status ?? ''} onValueChange={(v) => setMon(side, { status: v || null })}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Stat Points ({bootstrap.sp_max} each, {bootstrap.sp_budget} total)</label>
          <SpSpreadEditor sp={build.sp} onChange={(sp) => setMon(side, { sp })} spMax={bootstrap.sp_max} spBudget={bootstrap.sp_budget} />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Stat stage boosts (-6 to +6)</label>
          <BoostRow boosts={build.boosts} onChange={(boosts) => setMon(side, { boosts })} />
        </div>
      </CardContent>
    </Card>
  )
}
