"use client";

import { useState } from "react";
import { Button, FreeText, PageHeader, PageScaffold } from "@irontrust/ui";
import type { ClassificationRead } from "@irontrust/api-client";
import { useCreateUseCase } from "@/lib/intake";

export interface UseCaseCreateStepProps {
  systemId: string;
  usageContextId: string | null;
  humanOversightTypeId: string | null;
  dataCategoryIds: string[];
  affectedPartyIds: string[];
  onCreated: (useCaseId: string, classification: ClassificationRead) => void;
}

/**
 * WI-7 (create phase): POST /v1/use-cases. The branch on the response
 * (requires_context / prohibited / resolved) is encoded once, in the
 * wizard reducer (wizard-state.ts) — this component only creates and
 * hands the result up; it never reads `/lifecycle` itself (would mislabel
 * the court while requires_context is still open).
 */
export function UseCaseCreateStep({
  systemId,
  usageContextId,
  humanOversightTypeId,
  dataCategoryIds,
  affectedPartyIds,
  onCreated,
}: UseCaseCreateStepProps) {
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState("");
  const createUseCase = useCreateUseCase();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createUseCase.mutate(
      {
        system_id: systemId,
        title,
        purpose: purpose || null,
        context_blob: {},
        usage_context_id: usageContextId,
        human_oversight_type_id: humanOversightTypeId,
        data_category_ids: dataCategoryIds,
        affected_party_ids: affectedPartyIds,
      },
      {
        onSuccess: (data) => onCreated(data.use_case.id, data.classification),
      }
    );
  }

  return (
    <PageScaffold>
      <PageHeader title="Describe your use case" />
      <form aria-label="use-case-create" onSubmit={handleSubmit} className="border-hairline space-y-4 rounded-lg border p-4">
        <div className="space-y-1">
          <label htmlFor="use-case-title" className="text-sm font-medium">What are you using this for?</label>
          <input id="use-case-title" value={title} onChange={(e) => setTitle(e.target.value)} required className="border-hairline w-full rounded border px-3 py-1.5 text-sm" />
        </div>
        <FreeText id="use-case-purpose" label="Purpose (optional)" value={purpose} onChange={setPurpose} />

        {createUseCase.isError && (
          <div role="alert" className="text-sm text-danger">Could not register this use case. Check the form and try again.</div>
        )}

        <Button type="submit" disabled={createUseCase.isPending}>
          Continue
        </Button>
      </form>
    </PageScaffold>
  );
}
