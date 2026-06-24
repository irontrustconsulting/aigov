"use client";

import { useAssessmentDetail, useAssessmentSections } from "@/lib/assess";
import type { AssessmentStatus } from "@irontrust/api-client";
import { ItemCard } from "./item-card";

interface Props {
  assessmentId: string;
  assessmentStatus: AssessmentStatus;
  branch: "system_owner" | "contributor" | "reviewer" | "authoriser" | "auditor";
}

/**
 * AIIA body — section template + items grouped by section_key.
 * Feeder-surfaced items: source_assessment_id !== null → read-only (INV-16/PAT-7).
 * Status-based authoring lock (INV-31): DRAFT/NEEDS_REFRESH open; IN_REVIEW/APPROVED locked.
 */
export function AiiaBody({ assessmentId, assessmentStatus, branch }: Props) {
  const detailQuery = useAssessmentDetail(assessmentId);
  const sectionsQuery = useAssessmentSections(assessmentId);

  if (detailQuery.isLoading || sectionsQuery.isLoading) return <p>Loading assessment items…</p>;
  if (detailQuery.isError || !detailQuery.data || sectionsQuery.isError || !sectionsQuery.data) {
    return <p role="alert">Could not load assessment items.</p>;
  }

  const { items } = detailQuery.data;
  const sections = sectionsQuery.data;

  const isLocked = assessmentStatus === "in_review" || assessmentStatus === "approved";
  const isWriteRole = branch === "system_owner" || branch === "contributor";

  // Group items by section_key, preserving section order from template.
  const itemsBySection = new Map<string | null, typeof items>();
  for (const item of items) {
    const key = item.section_key;
    if (!itemsBySection.has(key)) itemsBySection.set(key, []);
    itemsBySection.get(key)!.push(item);
  }

  return (
    <section aria-label="assessment-body" className="space-y-8">
      {sections.map((section) => {
        const sectionItems = itemsBySection.get(section.section_key) ?? [];
        return (
          <div key={section.section_key} aria-label={`section-${section.section_key}`}>
            <h2 className="mb-2 text-lg font-semibold">
              {section.title}
              <span aria-label="applicability"> [{section.applicability}]</span>
            </h2>
            {section.prompt && <p className="text-ink-muted mb-3 text-sm">{section.prompt}</p>}

            {sectionItems.length === 0 ? (
              <p className="text-ink-muted text-sm">No items in this section yet.</p>
            ) : (
              <ul className="space-y-3">
                {sectionItems.map((item) => (
                  <li key={item.id}>
                    <ItemCard
                      item={item}
                      assessmentId={assessmentId}
                      isLocked={isLocked}
                      canWrite={isWriteRole && !isLocked}
                      isFederSurfaced={item.source_assessment_id !== null}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}

      {/* Items with no section_key (register facts etc.) */}
      {(itemsBySection.get(null) ?? []).length > 0 && (
        <div aria-label="section-unsectioned">
          <h2 className="mb-2 text-lg font-semibold">Other items</h2>
          <ul className="space-y-3">
            {(itemsBySection.get(null) ?? []).map((item) => (
              <li key={item.id}>
                <ItemCard
                  item={item}
                  assessmentId={assessmentId}
                  isLocked={isLocked}
                  canWrite={isWriteRole && !isLocked}
                  isFederSurfaced={item.source_assessment_id !== null}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
