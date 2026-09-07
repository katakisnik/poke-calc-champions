export function PokeBallIcon({ className = '', size = 28 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className={className} aria-hidden="true">
      <circle cx="20" cy="20" r="18" fill="white" stroke="black" strokeWidth="2.5" />
      <path d="M2 20a18 18 0 0 1 36 0Z" fill="currentColor" stroke="black" strokeWidth="2.5" />
      <line x1="2" y1="20" x2="38" y2="20" stroke="black" strokeWidth="2.5" />
      <circle cx="20" cy="20" r="6.5" fill="white" stroke="black" strokeWidth="2.5" />
      <circle cx="20" cy="20" r="3" fill="white" stroke="black" strokeWidth="2" />
    </svg>
  )
}
