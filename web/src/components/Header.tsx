import { motion } from 'motion/react'
import { PokeBallIcon } from '@/components/PokeBallIcon'
import { ManageTeamsDialog } from '@/components/ManageTeamsDialog'

/**
 * The building's roofline, not just a page title - a Center's exterior
 * is a red band over white walls; this is that same idea as a banner:
 * solid red, rounded bottom edge, white display-font title, with the
 * classic red/white ball as the one literal game reference.
 */
export function Header() {
  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      className="relative overflow-hidden rounded-b-2xl px-6 py-4 text-white shadow-lg sm:px-10"
      style={{ background: 'linear-gradient(135deg, var(--pc-red), var(--pc-red-dark))' }}
    >
      <div
        className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-10"
        style={{ background: 'white' }}
      />
      <div className="relative flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <motion.div
            initial={{ rotate: -35, scale: 0.7 }}
            animate={{ rotate: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 14, delay: 0.1 }}
          >
            <PokeBallIcon size={28} className="text-white drop-shadow" />
          </motion.div>
          <h1 className="font-display text-xl font-bold tracking-tight sm:text-2xl">
            Pokémon Champions Damage Calculator
          </h1>
        </div>
        <ManageTeamsDialog />
      </div>
    </motion.header>
  )
}
