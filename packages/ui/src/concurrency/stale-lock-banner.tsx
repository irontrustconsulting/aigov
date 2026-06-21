/** FE-6: the 412 surface. The resource changed since it was loaded — never
 * silently retry; invalidate, refetch, re-present, let the user retry. */
export function StaleLockBanner({ onReload }: { onReload: () => void }) {
  return (
    <div role="alert" className="bg-warning text-bg rounded-md p-3 text-sm">
      <p>This item changed since you loaded it. Reload to see the latest version before retrying.</p>
      <button type="button" onClick={onReload}>
        Reload
      </button>
    </div>
  );
}
