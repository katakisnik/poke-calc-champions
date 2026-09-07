import { create } from 'zustand'
import { api, type Bootstrap, type Preset, type SpeciesOut } from '@/api/client'

export interface MonBuild {
  species: string // species id, e.g. "garchomp"
  nature: string
  ability: string
  item: string | null // item id, or null
  sp: Record<string, number>
  boosts: Record<string, number>
  status: string | null
}

export type Side = 'a' | 'b'

export interface SideConditions {
  isHelpingHand: boolean
  isProtected: boolean
  reflect: boolean
  lightScreen: boolean
  auroraVeil: boolean
}

function emptySideConditions(): SideConditions {
  return { isHelpingHand: false, isProtected: false, reflect: false, lightScreen: false, auroraVeil: false }
}

const EMPTY_SP = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 }
const EMPTY_BOOSTS = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 }

function emptyMon(speciesId: string): MonBuild {
  return { species: speciesId, nature: 'Hardy', ability: '', item: null, sp: { ...EMPTY_SP }, boosts: { ...EMPTY_BOOSTS }, status: null }
}

/** The same suggested-set resolution selectSpecies() uses, factored out
 * so the initial mount (setBootstrap) seeds real suggested builds too,
 * not a placeholder Hardy/0-SP/no-item mon that then silently differs
 * from what a species change would have produced for the same species. */
function suggestedMon(species: SpeciesOut, bootstrap: Bootstrap, regulation: string): MonBuild {
  const ability = species.ability_slots.includes(species.ability) ? species.ability : species.ability_slots[0]

  let item: string | null
  if (species.mega_stone) {
    const stone = bootstrap.items.find((i) => i.name === species.mega_stone)
    item = stone?.id ?? null
  } else if (species.suggested_item) {
    const suggested = bootstrap.items.find((i) => i.name === species.suggested_item)
    item = suggested && isItemLegal(suggested.id, regulation, bootstrap) ? suggested.id : null
  } else {
    item = null
  }

  return {
    species: species.id,
    nature: species.suggested_nature,
    ability,
    item,
    sp: { ...EMPTY_SP, ...species.suggested_sp },
    boosts: { ...EMPTY_BOOSTS },
    status: null,
  }
}

export function isItemLegal(itemId: string | null, regulation: string, bootstrap: Bootstrap | null): boolean {
  if (!itemId || !bootstrap) return true
  if (regulation === 'M-B') return true
  const item = bootstrap.items.find((i) => i.id === itemId)
  return item?.legal_in_reg_m_a ?? true
}

interface CalcState {
  bootstrap: Bootstrap | null
  setBootstrap: (b: Bootstrap) => void
  speciesById: (id: string) => SpeciesOut | undefined

  regulation: string
  gameType: 'Singles' | 'Doubles'
  weather: string | null
  terrain: string | null
  isGravity: boolean
  setField: (patch: Partial<Pick<CalcState, 'regulation' | 'gameType' | 'weather' | 'terrain' | 'isGravity'>>) => void

  aSide: SideConditions
  bSide: SideConditions
  setSideConditions: (side: Side, patch: Partial<SideConditions>) => void

  a: MonBuild
  b: MonBuild
  setMon: (side: Side, patch: Partial<MonBuild>) => void
  /**
   * Species change reseeds nature/SP/item to that species' suggested set
   * (already computed server-side into bootstrap - see
   * routes_dex.py's _species_out) and ability to its own default -
   * porting Streamlit's "species change re-suggests, but a manual tweak
   * sticks until the NEXT species change" behavior. That behavior falls
   * out for free here: a manual edit is just a normal setMon() call, and
   * nothing overwrites it again until selectSpecies() runs next.
   */
  selectSpecies: (side: Side, speciesId: string) => void

  teams: Record<string, Preset[]>
  fetchTeams: () => Promise<void>
  /**
   * Populates species/nature/ability/item/SP straight from the preset -
   * unlike selectSpecies(), this deliberately bypasses suggestedMon() so
   * a loaded build isn't immediately overwritten by that species' own
   * suggestion. Boosts/status are battle-transient (Preset never carries
   * them - see data/teams.py) so they're left untouched, matching
   * ui/app.py's Load button which never touched those widgets either.
   */
  loadPreset: (side: Side, preset: Preset) => void
}

export const useCalcStore = create<CalcState>((set, get) => ({
  bootstrap: null,
  setBootstrap: (b) => {
    const regulation = get().regulation
    const garchomp = b.species.find((s) => s.id === 'garchomp')
    const tyranitar = b.species.find((s) => s.id === 'tyranitar')
    set({
      bootstrap: b,
      a: garchomp ? suggestedMon(garchomp, b, regulation) : emptyMon('garchomp'),
      b: tyranitar ? suggestedMon(tyranitar, b, regulation) : emptyMon('tyranitar'),
    })
  },
  speciesById: (id) => get().bootstrap?.species.find((s) => s.id === id),

  regulation: 'M-B',
  gameType: 'Doubles',
  weather: null,
  terrain: null,
  isGravity: false,
  setField: (patch) => set(patch),

  aSide: emptySideConditions(),
  bSide: emptySideConditions(),
  setSideConditions: (side, patch) =>
    set((s) => ({ [`${side}Side`]: { ...s[`${side}Side`], ...patch } }) as Partial<CalcState>),

  a: emptyMon('garchomp'),
  b: emptyMon('tyranitar'),
  setMon: (side, patch) => set((s) => ({ [side]: { ...s[side], ...patch } }) as Partial<CalcState>),

  selectSpecies: (side, speciesId) => {
    const { bootstrap, regulation } = get()
    const species = bootstrap?.species.find((sp) => sp.id === speciesId)
    if (!species || !bootstrap) {
      set((s) => ({ [side]: { ...s[side], species: speciesId } }) as Partial<CalcState>)
      return
    }

    // boosts/status are battle-transient, not part of a species'
    // "suggestion" - they carry over from whatever they were, matching
    // the Streamlit version's behavior (nothing there ever reset them
    // on a species change either).
    const suggested = suggestedMon(species, bootstrap, regulation)
    set((s) => ({
      [side]: { ...suggested, boosts: s[side].boosts, status: s[side].status },
    }) as Partial<CalcState>)
  },

  teams: {},
  fetchTeams: async () => {
    const { teams } = await api.getTeams()
    set({ teams })
  },
  loadPreset: (side, preset) =>
    set((s) => ({
      [side]: {
        ...s[side],
        species: preset.species,
        nature: preset.nature,
        ability: preset.ability,
        item: preset.item ?? null,
        sp: { ...EMPTY_SP, ...preset.sp },
      },
    }) as Partial<CalcState>),
}))
