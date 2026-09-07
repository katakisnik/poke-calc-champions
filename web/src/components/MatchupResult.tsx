import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { MoveCombobox } from '@/components/MoveCombobox'
import { TypeBadge } from '@/components/TypeBadge'
import { AnimatedNumber } from '@/components/AnimatedNumber'
import { RemainingHpBar } from '@/components/RemainingHpBar'
import { api, ApiError, type CalculateResult, type MoveOut } from '@/api/client'
import { toFieldPayload, toMonPayload } from '@/lib/buildPayload'
import { formatKoChances, moveInfoParts } from '@/lib/moveInfo'
import { useCalcStore, type Side } from '@/store/useCalcStore'
import { useDebounce } from '@/hooks/useDebounce'

function MoveInfo({ move }: { move: MoveOut }) {
  return (
    <div className="space-y-1">
      <TypeBadge type={move.type} />
      <p className="text-xs text-muted-foreground">{moveInfoParts(move).join(' · ')}</p>
      {move.description && <p className="text-xs text-muted-foreground">{move.description}</p>}
    </div>
  )
}

/** Damage range and KO chances on one line - the bar above already
 * shows remaining HP, so this is now just the supporting detail, not
 * two separate rows of it. */
function DamageDetailLine({ result }: { result: CalculateResult }) {
  const entries = formatKoChances(result.ko_chances)
  return (
    <p className="text-xs text-muted-foreground">
      <AnimatedNumber value={Math.min(...result.rolls)} />
      {'–'}
      <AnimatedNumber value={Math.max(...result.rolls)} /> dmg
      {' · '}
      {entries.map((entry, i) => (
        <span key={entry.hits}>
          {i > 0 && ' · '}
          {entry.isFinal ? <strong className="text-foreground">{entry.text}</strong> : entry.text}
        </span>
      ))}
    </p>
  )
}

/**
 * One attack direction (A attacks B, or B attacks A) - move picker, move
 * info, damage range, and KO-chance breakdown. Ported from ui/app.py's
 * render_matchup(). A Status move deals no direct damage
 * (calculate_damage() itself returns [0]*16 for these - a real, correct
 * early return) so the damage/KO section is skipped for those, matching
 * the original's is_status handling.
 */
export function MatchupResult({ attacker, defender, label }: { attacker: Side; defender: Side; label: string }) {
  const bootstrap = useCalcStore((s) => s.bootstrap)
  const attackerBuild = useCalcStore((s) => s[attacker])
  const defenderBuild = useCalcStore((s) => s[defender])
  const aSide = useCalcStore((s) => s.aSide)
  const bSide = useCalcStore((s) => s.bSide)
  const gameType = useCalcStore((s) => s.gameType)
  const weather = useCalcStore((s) => s.weather)
  const terrain = useCalcStore((s) => s.terrain)
  const isGravity = useCalcStore((s) => s.isGravity)

  const [moveId, setMoveId] = useState<string | null>(null)
  const [result, setResult] = useState<CalculateResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const attackerSpecies = useMemo(
    () => bootstrap?.species.find((s) => s.id === attackerBuild.species),
    [bootstrap, attackerBuild.species],
  )

  const learnableMoves = useMemo(() => {
    if (!bootstrap || !attackerSpecies) return []
    const ids = new Set(attackerSpecies.learnable_moves)
    return bootstrap.moves.filter((m) => ids.has(m.id))
  }, [bootstrap, attackerSpecies])

  // Reset the move pick when it's no longer legal for the (possibly new) attacker.
  useEffect(() => {
    if (moveId && !learnableMoves.some((m) => m.id === moveId)) setMoveId(null)
  }, [moveId, learnableMoves])

  const move = learnableMoves.find((m) => m.id === moveId) ?? null

  const debouncedAttacker = useDebounce(attackerBuild)
  const debouncedDefender = useDebounce(defenderBuild)
  const debouncedField = useDebounce({ gameType, weather, terrain, isGravity })

  useEffect(() => {
    if (!move || move.is_status) {
      setResult(null)
      return
    }
    let cancelled = false
    api
      .calculate({
        attacker: toMonPayload(debouncedAttacker),
        defender: toMonPayload(debouncedDefender),
        move_name: move.id,
        field: toFieldPayload(debouncedField, { a: aSide, b: bSide }, attacker, defender),
      })
      .then((r) => {
        if (!cancelled) {
          setResult(r)
          setError(null)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Failed to calculate')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [move?.id, debouncedAttacker, debouncedDefender, debouncedField, attacker, defender])

  const loPct = result ? (Math.min(...result.rolls) / result.defender_max_hp) * 100 : 0
  const hiPct = result ? (Math.max(...result.rolls) / result.defender_max_hp) * 100 : 0

  return (
    <Card className="pc-edge pc-edge-red gap-2 py-2.5">
      <CardHeader>
        <CardTitle className="font-display text-base">{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <MoveCombobox moves={learnableMoves} value={moveId} onChange={setMoveId} stabTypes={attackerSpecies?.types} />

        {move && <MoveInfo move={move} />}

        {move && move.is_status && (
          <p className="text-xs text-muted-foreground">Status move - no direct damage to show.</p>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {move && !move.is_status && result && (
          <div className="space-y-0.5">
            {/* The % of max HP is the number that actually matters ("does
                this KO"), so it's the hero here - the raw roll range is
                secondary detail, not the other way around like before. */}
            <p className="font-display text-3xl font-bold tabular-nums" style={{ color: 'var(--pc-red)' }}>
              <AnimatedNumber value={loPct} decimals={1} />
              {'–'}
              <AnimatedNumber value={hiPct} decimals={1} />%
            </p>
            <RemainingHpBar remainingLo={Math.max(0, 100 - hiPct)} remainingHi={Math.max(0, 100 - loPct)} />
            <DamageDetailLine result={result} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
