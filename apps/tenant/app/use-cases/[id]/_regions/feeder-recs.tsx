"use client";

import { useFeederRecs } from "@/lib/assess";
import type { SectionApplicability } from "@irontrust/api-client";

const APPLICABILITY_LABEL: Record<SectionApplicability, string> = {
  required: "Required",
  recommended: "Recommended",
  not_applicable: "Not applicable",
};

interface Props {
  assessmentId: string;
}

/**
 * Read-only feeder recommendations panel (A7 provisional defer).
 * Displays type, applicability, basis, and whether a feeder exists.
 */
export function FeederRecs({ assessmentId }: Props) {
  const query = useFeederRecs(assessmentId);

  if (query.isLoading) return null;
  if (query.isError || !query.data) return null;

  const recs = query.data.filter((r) => r.applicability !== "not_applicable");
  if (recs.length === 0) return null;

  return (
    <section aria-label="feeder-recommendations">
      <h2>Supplementary assessments</h2>
      <ul>
        {recs.map((rec) => (
          <li key={rec.type}>
            <strong>{rec.type.toUpperCase()}</strong>
            {" — "}
            {APPLICABILITY_LABEL[rec.applicability]}
            {rec.exists ? " (started)" : " (not yet started)"}
            <p>{rec.basis}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
