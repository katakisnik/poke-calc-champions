import { describe, expect, it } from 'vitest'
import { formatKoChances, moveInfoParts } from './moveInfo'
import type { MoveOut } from '@/api/client'

// Real values fetched from /api/bootstrap, not hand-typed - see the
// generator scripts under poke_calc/data/ for provenance.
function move(overrides: Partial<MoveOut>): MoveOut {
  return {
    id: 'x', name: 'X', type: 'Normal', category: 'Physical', base_power: 0,
    priority: 0, target: 'normal', flags: {}, multihit: null, has_secondary: false,
    drain: null, recoil: 0, breaks_protect: false, will_crit: false, crit_ratio: 1,
    description: null, is_status: false, is_spread: false,
    ...overrides,
  }
}

describe('moveInfoParts', () => {
  it('formats a plain spread move (Earthquake)', () => {
    const parts = moveInfoParts(move({
      category: 'Physical', base_power: 100, target: 'allAdjacent', is_spread: true,
    }))
    expect(parts).toEqual(['Physical', '100 BP', 'Hits all adjacent Pokemon'])
  })

  it('formats a recoil + contact move (Double-Edge)', () => {
    const parts = moveInfoParts(move({
      category: 'Physical', base_power: 120, flags: { contact: 1 }, recoil: 0.33,
    }))
    expect(parts).toEqual(['Physical', '120 BP', 'Contact', 'Recoil 33% of damage dealt'])
  })

  it('formats a guaranteed-crit move (Storm Throw)', () => {
    const parts = moveInfoParts(move({
      category: 'Physical', base_power: 60, flags: { contact: 1 }, will_crit: true,
    }))
    expect(parts).toEqual(['Physical', '60 BP', 'Contact', 'Always a critical hit'])
  })

  it('formats a multi-hit move (Bullet Seed)', () => {
    const parts = moveInfoParts(move({
      category: 'Physical', base_power: 25, flags: { bullet: 1 }, multihit: [2, 5],
    }))
    expect(parts).toEqual(['Physical', '25 BP', 'Bullet', 'Hits 2-5 times'])
  })

  it('shows "– BP" for a 0-power move rather than "0 BP"', () => {
    const parts = moveInfoParts(move({ category: 'Status', base_power: 0 }))
    expect(parts[1]).toBe('– BP')
  })

  it('ignores flags with no known label', () => {
    const parts = moveInfoParts(move({ flags: { protect: 1 } }))
    expect(parts).not.toContain('protect')
  })
})

describe('formatKoChances', () => {
  it('bolds (isFinal) only the entry that actually reached ~100%', () => {
    const entries = formatKoChances([
      { hits: 1, probability: 0 },
      { hits: 2, probability: 0.08 },
      { hits: 3, probability: 1.0 },
    ])
    expect(entries.map((e) => e.isFinal)).toEqual([false, false, true])
    expect(entries[0].text).toBe('OHKO 0%')
    expect(entries[2].text).toBe('3HKO 100%')
  })

  it('marks the last entry with a "+" when it never reaches certainty', () => {
    const entries = formatKoChances([
      { hits: 1, probability: 0 },
      { hits: 2, probability: 0 },
      { hits: 3, probability: 0.2 },
      { hits: 4, probability: 0.67 },
    ])
    expect(entries[3].text).toBe('4HKO+ 67%')
    expect(entries[3].isFinal).toBe(false)
  })

  it('a guaranteed OHKO is a single bolded entry', () => {
    const entries = formatKoChances([{ hits: 1, probability: 1.0 }])
    expect(entries).toEqual([{ hits: 1, text: 'OHKO 100%', isFinal: true }])
  })
})
