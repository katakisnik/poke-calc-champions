import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { Info } from 'lucide-react'
import { TERRAIN_INFO, WEATHER_INFO } from '@/lib/fieldInfo'
import { useCalcStore, type Side, type SideConditions } from '@/store/useCalcStore'

const NONE = '(none)'

function InfoTooltip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info className="h-3.5 w-3.5 shrink-0 cursor-help text-muted-foreground" />
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-sm leading-snug">{text}</TooltipContent>
    </Tooltip>
  )
}

const SIDE_CONDITION_FIELDS: { key: keyof SideConditions; label: string }[] = [
  { key: 'isHelpingHand', label: 'Helping Hand active' },
  { key: 'isProtected', label: 'Protected' },
  { key: 'reflect', label: 'Reflect' },
  { key: 'lightScreen', label: 'Light Screen' },
  { key: 'auroraVeil', label: 'Aurora Veil' },
]

function SideConditionsPanel({ side, label }: { side: Side; label: string }) {
  const conditions = useCalcStore((s) => (side === 'a' ? s.aSide : s.bSide))
  const setSideConditions = useCalcStore((s) => s.setSideConditions)

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {SIDE_CONDITION_FIELDS.map(({ key, label: fieldLabel }) => (
        <label key={key} className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={conditions[key]}
            onCheckedChange={(checked) => setSideConditions(side, { [key]: checked === true })}
          />
          {fieldLabel}
        </label>
      ))}
    </div>
  )
}

export function FieldControls() {
  const regulation = useCalcStore((s) => s.regulation)
  const gameType = useCalcStore((s) => s.gameType)
  const weather = useCalcStore((s) => s.weather)
  const terrain = useCalcStore((s) => s.terrain)
  const isGravity = useCalcStore((s) => s.isGravity)
  const setField = useCalcStore((s) => s.setField)
  const bootstrap = useCalcStore((s) => s.bootstrap)

  if (!bootstrap) return null

  return (
    <Card className="pc-edge pc-edge-blue gap-3 py-4">
      <CardHeader>
        <CardTitle className="font-display text-lg">Field</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Regulation</label>
            <Select value={regulation} onValueChange={(v) => setField({ regulation: v })}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {bootstrap.regulations.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Format</label>
            <div className="flex gap-1">
              {(['Singles', 'Doubles'] as const).map((gt) => (
                <Button
                  key={gt}
                  type="button"
                  size="sm"
                  variant={gameType === gt ? 'default' : 'outline'}
                  // The base Button variant sets shrink-0 (buttons never
                  // shrink by default), which overrides flex-1's implicit
                  // flex-shrink:1 - the button could grow but never shrink
                  // below "Doubles"'s text width, overflowing this narrow
                  // sidebar column. `shrink` overrides shrink-0 back, and
                  // min-w-0 clears the flex-item default min-width:auto
                  // that would otherwise still block shrinking below
                  // content size even with shrink enabled.
                  className="min-w-0 flex-1 shrink px-2 text-xs"
                  onClick={() => setField({ gameType: gt })}
                >
                  {gt}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground">Weather</label>
              {weather && <InfoTooltip text={WEATHER_INFO[weather]} />}
            </div>
            <Select value={weather ?? NONE} onValueChange={(v) => setField({ weather: v === NONE ? null : v })}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[NONE, ...bootstrap.weathers].map((w) => (
                  <SelectItem key={w} value={w}>
                    {w}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground">Terrain</label>
              {terrain && <InfoTooltip text={TERRAIN_INFO[terrain]} />}
            </div>
            <Select value={terrain ?? NONE} onValueChange={(v) => setField({ terrain: v === NONE ? null : v })}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[NONE, ...bootstrap.terrains].map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={isGravity} onCheckedChange={(checked) => setField({ isGravity: checked === true })} />
          Gravity
        </label>

        <div className="grid grid-cols-2 gap-4 border-t pt-3">
          <SideConditionsPanel side="a" label="Side A" />
          <SideConditionsPanel side="b" label="Side B" />
        </div>
      </CardContent>
    </Card>
  )
}
