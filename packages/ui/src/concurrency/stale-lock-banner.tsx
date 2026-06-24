/** FE-6: the 412 surface. The resource changed since it was loaded — never
 * silently retry; invalidate, refetch, re-present, let the user retry.
 * Amber left edge-bar (--verdict-attention) on a surface background. */
export function StaleLockBanner({ onReload }: { onReload: () => void }) {
  return (
    <div
      role="alert"
      data-concurrency="412"
      className="bg-surface rounded-sm p-3 text-sm text-ink"
      style={{ borderLeft: "3px solid var(--verdict-attention)" }}
    >
      <p>This item changed since you loaded it. Reload to see the latest version before retrying.</p>
      <button
        type="button"
        onClick={onReload}
        className="mt-2 text-sm font-medium text-brand underline"
      >
        Reload
      </button>
    </div>
  );
}
