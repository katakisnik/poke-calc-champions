import { useState } from 'react'
import { toast } from 'sonner'
import { BookmarkPlus } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError } from '@/api/client'
import { useCalcStore, type Side } from '@/store/useCalcStore'

const NEW_TEAM = '+ New team'

/**
 * Per-side "save/load this build" popover, triggered from a small icon
 * button rather than an always-visible panel - a floating overlay adds
 * no permanent height to the page, keeping the no-scroll layout intact.
 * Ported from ui/app.py's "Load from a saved team" / "Save this build to
 * a team" expanders (render_mon_panel()).
 */
export function TeamManager({ side, label }: { side: Side; label: string }) {
  const [open, setOpen] = useState(false)
  const teams = useCalcStore((s) => s.teams)
  const fetchTeams = useCalcStore((s) => s.fetchTeams)
  const loadPreset = useCalcStore((s) => s.loadPreset)
  const build = useCalcStore((s) => s[side])
  const speciesById = useCalcStore((s) => s.speciesById)
  const species = speciesById(build.species)

  const teamNames = Object.keys(teams).sort()

  const [loadTeam, setLoadTeam] = useState<string | null>(null)
  const [loadLabel, setLoadLabel] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [saveTeamChoice, setSaveTeamChoice] = useState(NEW_TEAM)
  const [newTeamName, setNewTeamName] = useState('')
  const [presetLabel, setPresetLabel] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)

  const activeLoadTeam = loadTeam && teams[loadTeam] ? loadTeam : teamNames[0]
  const activeLoadPresets = activeLoadTeam ? teams[activeLoadTeam] ?? [] : []
  const activeLoadLabel = loadLabel && activeLoadPresets.some((p) => p.label === loadLabel)
    ? loadLabel
    : activeLoadPresets[0]?.label

  function handleLoad() {
    const preset = activeLoadPresets.find((p) => p.label === activeLoadLabel)
    if (!preset) return
    // A preset's species is only an id in bootstrap.species by
    // convention, not a guarantee - a stale/hand-edited teams.json entry
    // (or a dex regenerated with different ids) could reference a
    // species that no longer resolves. Surface that instead of silently
    // handing MonPanel an unresolvable id, which makes the whole panel
    // vanish (species lookup there returns undefined -> early return).
    if (!speciesById(preset.species)) {
      setLoadError(`Saved species '${preset.species}' isn't in the current dex - this preset is stale.`)
      return
    }
    loadPreset(side, preset)
    toast.success(`Loaded '${preset.label}'.`)
    setLoadError(null)
    setOpen(false)
  }

  async function handleSave() {
    const teamName = (saveTeamChoice === NEW_TEAM ? newTeamName : saveTeamChoice).trim()
    if (!teamName) {
      setSaveError('Enter a team name first.')
      return
    }
    const label = presetLabel.trim() || species?.name || build.species
    try {
      const { teams: updated } = await api.putPreset(teamName, {
        label,
        species: build.species,
        nature: build.nature,
        ability: build.ability,
        item: build.item,
        sp: build.sp,
      })
      useCalcStore.setState({ teams: updated })
      setSaveError(null)
      setPresetLabel('')
      toast.success(`Saved '${label}' to '${teamName}'.`)
      setOpen(false)
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : 'Failed to save.')
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) fetchTeams()
      }}
    >
      <PopoverTrigger asChild>
        <Button type="button" variant="ghost" size="icon" className="size-7" aria-label={`Save/load ${label}`}>
          <BookmarkPlus className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <Tabs defaultValue="load">
          <TabsList className="w-full">
            <TabsTrigger value="load" className="flex-1">Load</TabsTrigger>
            <TabsTrigger value="save" className="flex-1">Save</TabsTrigger>
          </TabsList>

          <TabsContent value="load" className="space-y-2">
            {teamNames.length === 0 ? (
              <p className="text-xs text-muted-foreground">No saved teams yet - save a build below first.</p>
            ) : (
              <>
                <Select value={activeLoadTeam} onValueChange={(v) => { setLoadTeam(v); setLoadLabel(null); setLoadError(null) }}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Team" /></SelectTrigger>
                  <SelectContent>
                    {teamNames.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Select value={activeLoadLabel} onValueChange={(v) => { setLoadLabel(v); setLoadError(null) }}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Preset" /></SelectTrigger>
                  <SelectContent>
                    {activeLoadPresets.map((p, i) => (
                      <SelectItem key={`${p.label}-${i}`} value={p.label}>{p.label} ({p.species})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {loadError && <p className="text-xs text-destructive">{loadError}</p>}
                <Button type="button" variant="glow" size="sm" className="w-full" onClick={handleLoad} disabled={!activeLoadLabel}>
                  Load
                </Button>
              </>
            )}
          </TabsContent>

          <TabsContent value="save" className="space-y-2">
            <Select value={saveTeamChoice} onValueChange={setSaveTeamChoice}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NEW_TEAM}>{NEW_TEAM}</SelectItem>
                {teamNames.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
            {saveTeamChoice === NEW_TEAM && (
              <Input placeholder="New team name" value={newTeamName} onChange={(e) => setNewTeamName(e.target.value)} />
            )}
            <Input
              placeholder={species?.name ?? 'Preset name'}
              value={presetLabel}
              onChange={(e) => setPresetLabel(e.target.value)}
            />
            {saveError && <p className="text-xs text-destructive">{saveError}</p>}
            <Button type="button" variant="glow" size="sm" className="w-full" onClick={handleSave}>
              Save
            </Button>
          </TabsContent>
        </Tabs>
      </PopoverContent>
    </Popover>
  )
}
