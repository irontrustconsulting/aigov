/**
 * Shared terminal hard-stop render (WI-7 branch 2 / WI-8 PROHIBITED_HALT —
 * INV-26/33, D-7: prohibition is supreme from any state). No advance
 * control is rendered — there is nothing to barr or disable, the lifecycle
 * has no further forward edge from here.
 */
export function TerminalProhibited() {
  return (
    <section
      aria-label="terminal-prohibited"
      role="alert"
      className="mx-auto max-w-4xl space-y-8 px-6 py-8"
    >
      <div
        className="border-l-4 rounded-lg border p-4"
        style={{ borderColor: "var(--verdict-halt-fill)" }}
      >
        <h2 className="text-lg font-semibold mb-1">This use case cannot proceed</h2>
        <p className="text-ink-muted text-sm">
          It has been classified as a prohibited practice under the EU AI Act. This is a hard
          stop — there is no further action available on this use case.
        </p>
      </div>
    </section>
  );
}
