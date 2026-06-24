/** FE-6: the 409 surface. The action is no longer valid — the resource's
 * state moved on. Distinct from the 412 stale-lock case: the action is
 * void, not retryable after a reload. Ink left edge-bar, no retry affordance. */
export function BadFromStateBanner() {
  return (
    <div
      role="alert"
      data-concurrency="409"
      className="bg-surface rounded-sm p-3 text-sm text-ink"
      style={{ borderLeft: "3px solid var(--color-ink)" }}
    >
      <p>This action is no longer valid — the item&apos;s state has moved on since this view loaded.</p>
    </div>
  );
}
