"use client";

import { useState } from "react";
import { ProvenanceBadge, StaleLockBanner, BadFromStateBanner, SodAction } from "@irontrust/ui";
import {
  useAmendItem,
  useConfirmItem,
  useDeleteItem,
  StaleLockError,
  BadFromStateError,
} from "@/lib/assess";
import { ControlLinks } from "./control-links";
import { EvidenceManifest } from "./evidence-manifest";
import type { AssessmentItemRead, TreatmentDecision } from "@irontrust/api-client";

interface Props {
  item: AssessmentItemRead;
  assessmentId: string;
  /** True when assessment status is IN_REVIEW or APPROVED (INV-31). */
  isLocked: boolean;
  /** True when caller has gov:write AND assessment is not locked. */
  canWrite: boolean;
  /** True when item comes from a feeder (source_assessment_id !== null). */
  isFederSurfaced: boolean;
}

type ConcurrencyError = "stale" | "bad_state" | null;

/**
 * Per-item renderer — handles disposition (confirm/amend) and shows provenance.
 *
 * AI_SUGGESTED items: authoring fields are disabled until confirmed (PAT-8).
 * CATALOGUE_CURATED: exempt from the confirm-first gate (PAT-8).
 * Feeder-surfaced items: entirely read-only (INV-16/PAT-7).
 * 412/409: never collapsed — StaleLockBanner vs BadFromStateBanner (FE-6).
 * provenance is never sent in request bodies (INV-13).
 */
export function ItemCard({ item, assessmentId, isLocked, canWrite, isFederSurfaced }: Props) {
  const [concurrencyError, setConcurrencyError] = useState<ConcurrencyError>(null);
  const amendMutation = useAmendItem(assessmentId);
  const confirmMutation = useConfirmItem(assessmentId);
  const deleteMutation = useDeleteItem(assessmentId);

  const isAiSuggested = item.provenance === "ai_suggested";
  const isCatalogueCurated = item.provenance === "catalogue_curated";
  // Authoring fields blocked for AI_SUGGESTED until confirmed (CATALOGUE_CURATED exempt, PAT-8).
  const authoringBlocked = isAiSuggested && !isLocked && canWrite;

  function handleMutationError(err: unknown, type: "amend" | "confirm") {
    if (err instanceof StaleLockError) {
      setConcurrencyError("stale");
    } else if (err instanceof BadFromStateError) {
      setConcurrencyError("bad_state");
    }
  }

  function handleConfirm() {
    setConcurrencyError(null);
    confirmMutation.mutate(
      { itemId: item.id, lockVersion: item.lock_version },
      { onError: (err) => handleMutationError(err, "confirm") }
    );
  }

  function handleAmend(patch: Partial<Parameters<typeof amendMutation.mutate>[0]["body"]>) {
    setConcurrencyError(null);
    amendMutation.mutate(
      { itemId: item.id, body: patch, lockVersion: item.lock_version },
      { onError: (err) => handleMutationError(err, "amend") }
    );
  }

  function handleDelete() {
    deleteMutation.mutate(item.id);
  }

  const readOnly = isLocked || isFederSurfaced || !canWrite;

  return (
    <article aria-label={`item-${item.id}`} className="border-hairline rounded-lg border p-4 space-y-3">
      <ProvenanceBadge provenance={item.provenance} />

      {concurrencyError === "stale" && (
        <StaleLockBanner onReload={() => setConcurrencyError(null)} />
      )}
      {concurrencyError === "bad_state" && <BadFromStateBanner />}

      {/* Prompt / section context */}
      {item.prompt && <p className="text-ink-muted text-sm">{item.prompt}</p>}

      {/* Source ref (register facts, evidence manifest) — read-only display, no bytes */}
      {item.source_ref && (
        <p aria-label="source-ref" className="text-ink-muted text-sm">
          <em>Source: {item.source_ref}</em>
        </p>
      )}

      {/* Response field */}
      <div className="space-y-1">
        <label htmlFor={`response-${item.id}`} className="text-sm font-medium">Response</label>
        <textarea
          id={`response-${item.id}`}
          defaultValue={item.response ?? ""}
          disabled={readOnly || authoringBlocked}
          className="border-hairline w-full rounded border px-3 py-2 text-sm disabled:opacity-50"
          onBlur={(e) => {
            if (!readOnly && !authoringBlocked && e.target.value !== (item.response ?? "")) {
              handleAmend({ response: e.target.value || null });
            }
          }}
        />
      </div>

      {/* Treatment decision */}
      <div className="space-y-1">
        <label htmlFor={`treatment-${item.id}`} className="text-sm font-medium">Treatment</label>
        <select
          id={`treatment-${item.id}`}
          defaultValue={item.treatment_decision ?? ""}
          disabled={readOnly}
          className="border-hairline rounded border px-3 py-1.5 text-sm disabled:opacity-50"
          onChange={(e) => {
            if (!readOnly) {
              const val = e.target.value as TreatmentDecision | "";
              handleAmend({ treatment_decision: val || null });
            }
          }}
        >
          <option value="">—</option>
          <option value="mitigate">Mitigate</option>
          <option value="accept">Accept</option>
          <option value="transfer">Transfer</option>
          <option value="avoid">Avoid</option>
        </select>
      </div>

      {/* Confirm button: visible for AI_SUGGESTED when canWrite and not locked */}
      {isAiSuggested && canWrite && !isLocked && !isFederSurfaced && (
        <button
          onClick={handleConfirm}
          disabled={confirmMutation.isPending}
          aria-busy={confirmMutation.isPending}
          className="border-hairline rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {confirmMutation.isPending ? "Confirming…" : "Confirm"}
        </button>
      )}

      {/* Control links (WI-5) — free on any item, including AI_SUGGESTED (INV-20) */}
      <ControlLinks
        item={item}
        assessmentId={assessmentId}
        canWrite={canWrite && !isLocked}
      />

      {/* Evidence manifest (UI-F5-EVIDENCE WI-E) — disposition-gated for AI_SUGGESTED (DF5-5) */}
      <EvidenceManifest
        item={item}
        assessmentId={assessmentId}
        canWrite={canWrite && !isLocked && !isFederSurfaced}
      />

      {/* Delete — absent when locked (INV-31); feeder-surfaced items have no delete affordance */}
      {canWrite && !isLocked && !isFederSurfaced && (
        <SodAction barred={false}>
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            aria-busy={deleteMutation.isPending}
            className="border-hairline rounded border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete item"}
          </button>
        </SodAction>
      )}
    </article>
  );
}
