import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { MonPanel } from '@/components/MonPanel'
import { FieldControls } from '@/components/FieldControls'
import { SpeedComparison } from '@/components/SpeedComparison'
import { MatchupResult } from '@/components/MatchupResult'
import { Header } from '@/components/Header'
import { PokeBallIcon } from '@/components/PokeBallIcon'
import { api } from '@/api/client'
import { useCalcStore } from '@/store/useCalcStore'

const sectionMotion = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
}

export default function App() {
  const setBootstrap = useCalcStore((s) => s.setBootstrap)
  const bootstrap = useCalcStore((s) => s.bootstrap)
  const fetchTeams = useCalcStore((s) => s.fetchTeams)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .bootstrap()
      .then(setBootstrap)
      .catch((e) => setError(e.message))
    fetchTeams().catch(() => {})
  }, [setBootstrap, fetchTeams])

  if (error) {
    return <div className="p-8 text-destructive">Failed to load: {error}</div>
  }
  if (!bootstrap) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
          <PokeBallIcon size={40} className="text-destructive" />
        </motion.div>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <Header />
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
          <motion.aside
            {...sectionMotion}
            transition={{ duration: 0.4, delay: 0.05 }}
            className="space-y-6 lg:sticky lg:top-6 lg:self-start"
          >
            <FieldControls />
            <SpeedComparison />
          </motion.aside>

          {/* Each Pokemon's build sits directly above its own attack
              result - using the screen's width instead of stacking
              Speed/matchups in their own full-width rows below, so a
              normal wide screen doesn't need to scroll to see everything. */}
          <main className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <motion.div {...sectionMotion} transition={{ duration: 0.4, delay: 0.1 }} className="space-y-3">
              <MonPanel side="a" label="Pokémon A" />
              <MatchupResult attacker="a" defender="b" label="A attacks B" />
            </motion.div>

            <motion.div {...sectionMotion} transition={{ duration: 0.4, delay: 0.15 }} className="space-y-3">
              <MonPanel side="b" label="Pokémon B" />
              <MatchupResult attacker="b" defender="a" label="B attacks A" />
            </motion.div>
          </main>
        </div>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
