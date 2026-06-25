export function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      className={["animate-pulse rounded bg-surface-sunken", className].join(" ")}
      aria-hidden="true"
    />
  );
}

export function Skeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div
      className={["space-y-3", className].join(" ")}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBlock
          key={i}
          className={i === 0 ? "h-5 w-1/2" : i % 3 === 2 ? "h-4 w-2/3" : "h-4 w-full"}
        />
      ))}
    </div>
  );
}
