import { useEffect, useState } from 'react'

/** Debounces any value by re-emitting it only after `delayMs` of no
 * further changes - used to avoid firing an API call on every single
 * keystroke/slider-drag tick (see the migration plan: "only /api/calculate
 * round-trips (debounced ~150ms)"). */
export function useDebounce<T>(value: T, delayMs = 150): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
