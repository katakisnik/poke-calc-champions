import { useState } from 'react'
import { toast } from 'sonner'
import { ListTree, Trash2 } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { api } from '@/api/client'
import { useCalcStore } from '@/store/useCalcStore'

/**
 * Global "delete a saved team/preset" dialog - a Dialog scrolls
 * internally (max-h + overflow-y-auto) rather than pushing the page
 * taller, so an arbitrarily long team list never reintroduces the
 * page-level scrolling the layout was just fixed to avoid.
 * Ported from ui/app.py's "Manage Teams" expander (bottom of the page).
 */
export function ManageTeamsDialog() {
  const [open, setOpen] = useState(false)
  const teams = useCalcStore((s) => s.teams)
  const fetchTeams = useCalcStore((s) => s.fetchTeams)
  const teamNames = Object.keys(teams).sort()

  async function deletePreset(teamName: string, index: number) {
    const { teams: updated } = await api.deletePreset(teamName, index)
    useCalcStore.setState({ teams: updated })
  }

  async function deleteTeam(teamName: string) {
    const { teams: updated } = await api.deleteTeam(teamName)
    useCalcStore.setState({ teams: updated })
    toast.success(`Deleted team '${teamName}'.`)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) fetchTeams()
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="ghost" size="icon" className="size-8 text-white hover:bg-white/15 hover:text-white">
          <ListTree className="size-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display">Manage Teams</DialogTitle>
        </DialogHeader>

        {teamNames.length === 0 ? (
          <p className="text-sm text-muted-foreground">No saved teams yet.</p>
        ) : (
          <div className="space-y-4">
            {teamNames.map((teamName) => (
              <div key={teamName} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="font-display text-sm font-semibold">{teamName}</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive hover:text-destructive"
                    onClick={() => deleteTeam(teamName)}
                  >
                    Delete team
                  </Button>
                </div>
                {teams[teamName].map((preset, i) => (
                  <div key={`${preset.label}-${i}`} className="flex items-center justify-between rounded-md border px-2.5 py-1.5 text-sm">
                    <span>
                      {preset.label} <span className="text-xs text-muted-foreground">({preset.species})</span>
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-6 text-muted-foreground hover:text-destructive"
                      aria-label={`Delete ${preset.label}`}
                      onClick={() => deletePreset(teamName, i)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
