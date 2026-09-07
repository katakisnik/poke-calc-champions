import { beforeEach, describe, expect, it } from 'vitest'
import { useCalcStore, isItemLegal } from './useCalcStore'
import type { Bootstrap } from '@/api/client'
import fixture from './__fixtures__/bootstrap.fixture.json'

const bootstrap = fixture as unknown as Bootstrap

/**
 * These lock in exactly the "subtle state behaviors" the migration plan
 * flagged as the real risk of this rewrite (species change reseeds
 * nature/SP/item but a manual tweak sticks; Mega formes force their own
 * stone; boosts/status survive a species change) - the same behaviors
 * tests/test_ui.py's AppTest suite verified on the Streamlit side.
 */
describe('useCalcStore', () => {
  beforeEach(() => {
    useCalcStore.setState({
      bootstrap: null,
      regulation: 'M-B',
      gameType: 'Singles',
      weather: null,
      terrain: null,
      isGravity: false,
    })
  })

  it('seeds both sides with real suggested builds on bootstrap load, not placeholders', () => {
    useCalcStore.getState().setBootstrap(bootstrap)
    const { a, b } = useCalcStore.getState()
    expect(a.species).toBe('garchomp')
    expect(a.nature).toBe('Jolly') // real ladder data, not a Hardy/0-SP placeholder
    expect(a.item).toBe('lifeorb')
    expect(b.species).toBe('tyranitar')
  })

  it('selectSpecies reseeds nature/ability/item/sp to the new species suggestion', () => {
    useCalcStore.getState().setBootstrap(bootstrap)
    useCalcStore.getState().setMon('a', { nature: 'Adamant' }) // a manual tweak
    useCalcStore.getState().selectSpecies('a', 'tyranitar')
    const a = useCalcStore.getState().a
    expect(a.species).toBe('tyranitar')
    expect(a.nature).not.toBe('Adamant') // overwritten by the new species' own suggestion
  })

  it('a manual tweak survives an unrelated setMon call (does not get clobbered)', () => {
    useCalcStore.getState().setBootstrap(bootstrap)
    useCalcStore.getState().setMon('a', { nature: 'Adamant' })
    useCalcStore.getState().setMon('a', { status: 'brn' })
    expect(useCalcStore.getState().a.nature).toBe('Adamant')
  })

  it('boosts and status survive a species change (battle-transient, not part of the suggestion)', () => {
    useCalcStore.getState().setBootstrap(bootstrap)
    useCalcStore.getState().setMon('a', { boosts: { atk: 2, def: 0, spa: 0, spd: 0, spe: 0 }, status: 'par' })
    useCalcStore.getState().selectSpecies('a', 'tyranitar')
    const a = useCalcStore.getState().a
    expect(a.boosts.atk).toBe(2)
    expect(a.status).toBe('par')
  })

  it('a Mega forme forces its own Mega Stone regardless of the suggested item', () => {
    useCalcStore.getState().setBootstrap(bootstrap)
    useCalcStore.getState().selectSpecies('a', 'garchompmega')
    expect(useCalcStore.getState().a.item).toBe('garchompite')
  })

  it('an item illegal under the current Regulation falls back to none', () => {
    useCalcStore.setState({ regulation: 'M-A' })
    useCalcStore.getState().setBootstrap(bootstrap)
    // Life Orb (Garchomp's suggested item) is M-A-banned.
    expect(useCalcStore.getState().a.item).toBeNull()
  })
})

describe('isItemLegal', () => {
  it('anything is legal under M-B', () => {
    expect(isItemLegal('lifeorb', 'M-B', bootstrap)).toBe(true)
  })

  it('Life Orb is banned under M-A, Choice Scarf is not', () => {
    expect(isItemLegal('lifeorb', 'M-A', bootstrap)).toBe(false)
    expect(isItemLegal('choicescarf', 'M-A', bootstrap)).toBe(true)
  })

  it('no item held is always legal', () => {
    expect(isItemLegal(null, 'M-A', bootstrap)).toBe(true)
  })
})
