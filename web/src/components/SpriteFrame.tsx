/**
 * A fixed-size sprite frame with object-contain, ported from ui/app.py's
 * render_sprite() - same reasoning: a raw sprite image's own aspect
 * ratio varies wildly across species (Wailord vs. Diglett), so every
 * sprite gets the same visual footprint here regardless of its native
 * size.
 */
export function SpriteFrame({ url, size = 112 }: { url: string | null | undefined; size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-lg bg-black/5 dark:bg-white/5"
      style={{ width: size, height: size }}
    >
      {url ? <img src={url} alt="" className="max-h-full max-w-full object-contain" /> : null}
    </div>
  )
}
