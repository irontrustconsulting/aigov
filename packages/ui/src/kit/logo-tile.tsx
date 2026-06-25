export interface LogoTileProps {
  src?: string | null;
  name: string;
  size?: number;
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/);
  return words
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** LogoTile (FE-25) — renders a logo image when src is present; falls back to
 *  a 1–2 character monogram from name. Neutral ramp only. */
export function LogoTile({ src, name, size = 40 }: LogoTileProps) {
  const style = { width: size, height: size, minWidth: size } as const;
  if (src) {
    return (
      <span
        aria-label={name}
        style={style}
        className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-hairline bg-surface"
      >
        <img src={src} alt={name} className="h-full w-full object-contain" />
      </span>
    );
  }
  return (
    <span
      aria-label={name}
      style={style}
      className="inline-flex shrink-0 items-center justify-center rounded-md border border-hairline bg-surface-sunken text-xs font-semibold text-ink-muted"
    >
      {initials(name)}
    </span>
  );
}
