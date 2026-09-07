import { useEffect } from 'react'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'

/** A number that eases toward its new value instead of snapping - makes
 * Speed/damage updates (triggered by any build/field change) read as a
 * live recalculation rather than a jarring text swap. */
export function AnimatedNumber({
  value,
  decimals = 0,
  className = '',
}: {
  value: number
  decimals?: number
  className?: string
}) {
  const motionValue = useMotionValue(value)
  const rounded = useTransform(motionValue, (v) => v.toFixed(decimals))

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.4, ease: 'easeOut' })
    return () => controls.stop()
  }, [value, motionValue])

  return (
    <motion.span className={className} initial={false}>
      {rounded}
    </motion.span>
  )
}
