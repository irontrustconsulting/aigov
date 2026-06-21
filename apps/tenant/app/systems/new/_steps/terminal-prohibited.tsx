/**
 * Shared terminal hard-stop render (WI-7 branch 2 / WI-8 PROHIBITED_HALT —
 * INV-26/33, D-7: prohibition is supreme from any state). No advance
 * control is rendered — there is nothing to barr or disable, the lifecycle
 * has no further forward edge from here.
 */
export function TerminalProhibited() {
  return (
    <section aria-label="terminal-prohibited" role="alert">
      <h2>This use case cannot proceed</h2>
      <p>
        It has been classified as a prohibited practice under the EU AI Act. This is a hard
        stop — there is no further action available on this use case.
      </p>
    </section>
  );
}
