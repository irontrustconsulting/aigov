import { SystemDetailClient } from "./system-detail-client";

/**
 * Thin Server Component: Next 15 requires awaiting the dynamic route's
 * `params` Promise. Resolved synchronously here so the interactive surface
 * (`SystemDetailClient`) takes a plain `systemId` string — no client-side
 * `use()`/Suspense plumbing, and directly unit-testable like F1's step
 * components.
 */
export default async function SystemDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SystemDetailClient systemId={id} />;
}
