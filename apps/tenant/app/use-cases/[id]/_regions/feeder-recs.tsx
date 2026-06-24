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
      <h2 className="mb-2 text-lg font-semibold">Supplementary assessments</h2>
      <ul className="space-y-3">
        {recs.map((rec) => (
          <li key={rec.type} className="border-hairline rounded-lg border p-4">
            <strong className="text-sm">{rec.type.toUpperCase()}</strong>
            <span className="text-ink-muted text-sm">
              {" — "}
              {APPLICABILITY_LABEL[rec.applicability]}
              {rec.exists ? " (started)" : " (not yet started)"}
            </span>
            <p className="text-ink-muted mt-1 text-sm">{rec.basis}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
