/** FE-6: the 409 surface. The action is no longer valid — the resource's
 * state moved on. Distinct from the 412 stale-lock case: the action is
 * void, not retryable after a reload. */
export function BadFromStateBanner() {
  return (
    <div role="alert" className="bg-danger text-bg rounded-md p-3 text-sm">
      <p>This action is no longer valid — the item&apos;s state has moved on since this view loaded.</p>
    </div>
  );
}
