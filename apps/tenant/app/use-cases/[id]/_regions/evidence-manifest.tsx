"use client";

import { EvidenceManifestChip, EvidenceLinkPicker, SodAction } from "@irontrust/ui";
import { useLinkEvidence, useUnlinkEvidence } from "@/lib/assess";
import { useEvidenceList } from "@/lib/evidence";
import type { AssessmentItemRead } from "@irontrust/api-client";

interface Props {
  item: AssessmentItemRead;
  assessmentId: string;
  /** True when assessment is not locked and caller has gov:write. */
  canWrite: boolean;
}

/**
 * Per-item evidence manifest and link/unlink controls (UI-F5-EVIDENCE WI-E).
 * Renders item.evidence_links (self-describing — no download_url, DF5-3/DF5-8).
 *
 * Link is disposition-gated: AI_SUGGESTED items show the button disabled-with-reason
 * (INV-20, DF5-5). When not AI_SUGGESTED, EvidenceLinkPicker self-manages open state.
 * Feeder-surfaced items: callers pass canWrite=false → manifest read-only.
 * Unlink targets evidence_id, not the link-row id (DF5-9).
 * Invalidates AIIA-detail only; lifecycle key NOT invalidated (DF5-10, D-29).
 */
export function EvidenceManifest({ item, assessmentId, canWrite }: Props) {
  const listQuery = useEvidenceList();
  const linkMutation = useLinkEvidence(assessmentId);
  const unlinkMutation = useUnlinkEvidence(assessmentId);

  const isAiSuggested = item.provenance === "ai_suggested";
  const linkedIds = new Set(item.evidence_links.map((l) => l.evidence_id));

  const pickerItems = (listQuery.data?.items ?? [])
    .filter((ev) => !linkedIds.has(ev.id))
    .map((ev) => ({
      id: ev.id,
      title: ev.title,
      sha256: ev.sha256,
      content_type: ev.content_type,
    }));

  function handleUnlink(evidenceId: string) {
    unlinkMutation.mutate({ itemId: item.id, evidenceId });
  }

  return (
    <div aria-label="evidence-manifest">
      {item.evidence_links.length > 0 && (
        <ul aria-label="linked-evidence" className="flex flex-wrap gap-1">
          {item.evidence_links.map((link) => (
            <li key={link.evidence_id}>
              <EvidenceManifestChip
                link={link}
                onUnlink={canWrite ? handleUnlink : undefined}
              />
            </li>
          ))}
        </ul>
      )}

      {/* Disposition gate: show picker only for non-AI_SUGGESTED; show blocked stub otherwise */}
      {canWrite && isAiSuggested && (
        <SodAction
          barred={false}
          blockedReason="Confirm or amend this item before linking evidence"
        >
          <button type="button" className="text-sm underline">
            Link evidence…
          </button>
        </SodAction>
      )}

      {canWrite && !isAiSuggested && (
        <EvidenceLinkPicker
          items={pickerItems}
          isLoading={listQuery.isLoading}
          onLink={(evidenceId) => linkMutation.mutate({ itemId: item.id, evidenceId })}
          isPending={linkMutation.isPending}
        />
      )}
    </div>
  );
}
