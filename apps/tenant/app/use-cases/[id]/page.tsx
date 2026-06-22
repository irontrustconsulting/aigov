import { AssessmentPageClient } from "./assessment-page-client";

/** Thin RSC: awaits dynamic-route params (Next 15) and passes a plain string
 * down to the interactive surface — no client-side use()/Suspense needed. */
export default async function UseCasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssessmentPageClient useCaseId={id} />;
}
