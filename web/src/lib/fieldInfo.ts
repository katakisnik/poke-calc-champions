/**
 * What each field condition actually does - ported verbatim from
 * ui/app.py's WEATHER_INFO/TERRAIN_INFO. Per-turn effects this engine
 * doesn't compute (residual chip damage, Grassy Terrain's healing,
 * terrain's 5-turn duration) are called out explicitly rather than
 * implied - see engine/damage.py for exactly what IS modeled.
 */
export const WEATHER_INFO: Record<string, string> = {
  Sun: "Fire-type moves deal 1.5x damage, Water-type moves deal 0.5x. Solar Beam/Solar Blade skip their charge turn (Sun is their OWN good weather, so they're never halved either). Powers Chlorophyll (2x Speed) and Solar Power (1.5x Sp. Atk, but the holder loses 1/8 max HP each turn - not simulated here).",
  Rain: 'Water-type moves deal 1.5x damage, Fire-type moves deal 0.5x. Thunder and Hurricane never miss. Powers Swift Swim (2x Speed).',
  Sand: 'Rock-types get a 1.5x Sp. Def boost. Non-Rock/Ground/Steel types lose 1/16 max HP each turn (not simulated here). Powers Sand Rush (2x Speed) and Sand Force (1.3x power for Rock/Ground/Steel moves).',
  Snow: 'Ice-types get a 1.5x Defense boost. Non-Ice types lose 1/16 max HP each turn (not simulated here). Powers Slush Rush (2x Speed).',
}

export const TERRAIN_INFO: Record<string, string> = {
  Electric: "Electric-type moves get a 1.3x power boost from a grounded attacker. Grounded Pokemon can't fall asleep. Powers Surge Surfer (2x Speed). Only affects grounded Pokemon; lasts 5 turns (duration not tracked here).",
  Grassy: 'Grass-type moves get a 1.3x power boost from a grounded attacker, and deal half damage from Earthquake/Bulldoze/Magnitude against a grounded defender. Grounded Pokemon heal 1/16 max HP each turn (not simulated here). Only affects grounded Pokemon; lasts 5 turns (duration not tracked here).',
  Misty: "Dragon-type moves deal half damage against a grounded defender. Grounded Pokemon can't be inflicted with a major status condition. Only affects grounded Pokemon; lasts 5 turns (duration not tracked here).",
  Psychic: 'Psychic-type moves get a 1.3x power boost from a grounded attacker. Grounded Pokemon are protected from moves with increased priority. Only affects grounded Pokemon; lasts 5 turns (duration not tracked here).',
}

export const MOVE_FLAG_LABELS: Record<string, string> = {
  contact: 'Contact',
  bullet: 'Bullet',
  bite: 'Bite',
  pulse: 'Pulse',
  punch: 'Punch',
  slicing: 'Slicing',
  sound: 'Sound',
  wind: 'Wind',
}

export const KO_ORDINAL_LABELS: Record<number, string> = { 1: 'OHKO', 2: '2HKO', 3: '3HKO', 4: '4HKO', 5: '5HKO' }
