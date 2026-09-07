import type { FieldPayload, MonBuildPayload } from '@/api/client'
import type { MonBuild, Side, SideConditions } from '@/store/useCalcStore'

/** MonBuild's shape already matches the API's MonBuildIn field-for-field -
 * always full HP, same as the rest of this project (no in-battle HP
 * tracking anywhere, see the original ui/app.py's current_hp_fraction
 * comment). */
export function toMonPayload(build: MonBuild): MonBuildPayload {
  return {
    species: build.species,
    ability: build.ability,
    item: build.item,
    nature: build.nature,
    sp: build.sp,
    boosts: build.boosts,
    status: build.status,
    current_hp_fraction: 1.0,
  }
}

function toSidePayload(sc: SideConditions) {
  return {
    side_conditions: [
      ...(sc.reflect ? ['reflect'] : []),
      ...(sc.lightScreen ? ['lightscreen'] : []),
      ...(sc.auroraVeil ? ['auroraveil'] : []),
    ],
    is_protected: sc.isProtected,
    is_helping_hand: sc.isHelpingHand,
  }
}

/** Builds the field payload for one attack direction - `attacker`/
 * `defender` say which side (A or B) is attacking here, so
 * attacker_side/defender_side land on the right SideConditions
 * regardless of which physical Pokemon is doing the attacking. Ported
 * from ui/app.py's field_a_to_b/field_b_to_a construction. */
export function toFieldPayload(
  field: { gameType: string; weather: string | null; terrain: string | null; isGravity: boolean },
  sides: { a: SideConditions; b: SideConditions },
  attacker: Side,
  defender: Side,
): FieldPayload {
  return {
    game_type: field.gameType,
    weather: field.weather,
    terrain: field.terrain,
    is_gravity: field.isGravity,
    attacker_side: toSidePayload(sides[attacker]),
    defender_side: toSidePayload(sides[defender]),
  }
}
