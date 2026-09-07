import { useEffect, useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { AnimatedNumber } from '@/components/AnimatedNumber'
import { api, ApiError, type SpeedResult } from '@/api/client'
import { toFieldPayload, toMonPayload } from '@/lib/buildPayload'
import { useCalcStore } from '@/store/useCalcStore'
import { useDebounce } from '@/hooks/useDebounce'

/**
 * Who moves first - current (stage-boosted, item/ability/weather/
 * paralysis-adjusted) Speed, not base Speed. Ported from ui/app.py's
 * render_speed_comparison(). Deliberately move-independent (see
 * /api/speed's own docstring) - this shows before either side has picked
 * a move, same as the original.
 */
export function SpeedComparison() {
  const a = useCalcStore((s) => s.a)
  const b = useCalcStore((s) => s.b)
  const aSide = useCalcStore((s) => s.aSide)
  const bSide = useCalcStore((s) => s.bSide)
  const gameType = useCalcStore((s) => s.gameType)
  const weather = useCalcStore((s) => s.weather)
  const terrain = useCalcStore((s) => s.terrain)
  const isGravity = useCalcStore((s) => s.isGravity)

  const debouncedA = useDebounce(a)
  const debouncedB = useDebounce(b)
  const debouncedField = useDebounce({ gameType, weather, terrain, isGravity })

  const [result, setResult] = useState<SpeedResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .speed({
        attacker: toMonPayload(debouncedA),
        defender: toMonPayload(debouncedB),
        field: toFieldPayload(debouncedField, { a: aSide, b: bSide }, 'a', 'b'),
      })
      .then((r) => {
        if (!cancelled) {
          setResult(r)
          setError(null)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Failed to compute speed')
      })
    return () => {
      cancelled = true
    }
    // aSide/bSide don't affect speed, only included via debouncedField's dependents indirectly - omitted intentionally
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedA, debouncedB, debouncedField])

  if (error) return <p className="text-sm text-destructive">{error}</p>
  if (!result) return null

  const { attacker_speed: aSpeed, defender_speed: bSpeed } = result
  const tie = aSpeed === bSpeed
  const faster = aSpeed > bSpeed ? 'A' : 'B'
  const diff = Math.abs(aSpeed - bSpeed)

  return (
    // 2 columns for the numbers (fits a narrow sidebar) with the "who's
    // faster" caption below, rather than 3-across - a 3-column layout
    // squeezed that middle caption uncomfortably once this moved into
    // the sidebar alongside Field.
    <Card className="pc-edge pc-edge-blue py-4">
      <CardContent className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div className="text-center">
            <p className="text-xs text-muted-foreground">Pokémon A</p>
            <AnimatedNumber value={aSpeed} className="font-display text-2xl font-bold tabular-nums" />
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground">Pokémon B</p>
            <AnimatedNumber value={bSpeed} className="font-display text-2xl font-bold tabular-nums" />
          </div>
        </div>
        <p className="text-center text-xs text-muted-foreground">
          {tie ? 'Speed tie - coin flip for who moves first' : `Pokémon ${faster} moves first (+${diff} Speed)`}
        </p>
      </CardContent>
    </Card>
  )
}
