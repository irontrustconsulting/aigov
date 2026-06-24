"use client";

import { useState } from "react";
import { Button, FreeText } from "@irontrust/ui";
import type { ClassificationRead } from "@irontrust/api-client";
import { useCreateUseCase } from "@/lib/intake";

export interface UseCaseCreateStepProps {
  systemId: string;
  onCreated: (useCaseId: string, classification: ClassificationRead) => void;
}

/**
 * WI-7 (create phase): POST /v1/use-cases. The branch on the response
 * (requires_context / prohibited / resolved) is encoded once, in the
 * wizard reducer (wizard-state.ts) — this component only creates and
 * hands the result up; it never reads `/lifecycle` itself (would mislabel
 * the court while requires_context is still open).
 */
export function UseCaseCreateStep({ systemId, onCreated }: UseCaseCreateStepProps) {
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState("");
  const createUseCase = useCreateUseCase();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createUseCase.mutate(
      { system_id: systemId, title, purpose: purpose || null, context_blob: {} },
      {
        onSuccess: (data) => onCreated(data.use_case.id, data.classification),
      }
    );
  }

  return (
    <form aria-label="use-case-create" onSubmit={handleSubmit} className="border-hairline mx-auto max-w-4xl space-y-4 rounded-lg border p-4">
      <div className="space-y-1">
        <label htmlFor="use-case-title" className="text-sm font-medium">What are you using this for?</label>
        <input id="use-case-title" value={title} onChange={(e) => setTitle(e.target.value)} required className="border-hairline w-full rounded border px-3 py-1.5 text-sm" />
      </div>
      <FreeText id="use-case-purpose" label="Purpose (optional)" value={purpose} onChange={setPurpose} />

      {createUseCase.isError && (
        <p role="alert">Could not register this use case. Check the form and try again.</p>
      )}

      <Button type="submit" disabled={createUseCase.isPending}>
        Continue
      </Button>
    </form>
  );
}
