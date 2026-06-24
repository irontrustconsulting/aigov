/**
 * WI-10: reviewer/authoriser/auditor reaching the create-wizard — assurance
 * read, capture controls absent. This surface is adoption-face capture
 * (UX.md §2); the assurance face's own queues/views are a separate surface,
 * out of F1 scope.
 */
export function AssuranceReadOnly() {
  return (
    <section aria-label="assurance-read-only" className="mx-auto max-w-4xl space-y-8 px-6 py-8">
      <p className="text-ink-muted text-sm">
        This is a capture surface for registering a new system. There is nothing for your role to
        review here yet — assessments you review will appear in the review queue once one exists.
      </p>
    </section>
  );
}
