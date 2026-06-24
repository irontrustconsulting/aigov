/**
 * WI-10: a contributor (or any member without system_owner) landing on the
 * create-wizard directly — there is nothing here for them to act on yet
 * (creating a system/use case is system_owner-only). An empty-state, not a
 * dead control (FE-8's "absent, not disabled" extended to a whole surface).
 */
export function NeedsSystemOwner() {
  return (
    <section aria-label="needs-system-owner" className="mx-auto max-w-4xl space-y-8 px-6 py-8">
      <p className="text-ink-muted text-sm">
        Starting a new system needs a system owner. Once a system owner registers it, you&apos;ll
        be able to help with any classification questions it raises.
      </p>
    </section>
  );
}
