"use client";

import { useState, type FormEvent } from "react";
import { Button, FreeText, SingleSelect, SodAction, type SelectOption } from "@irontrust/ui";
import type { AnswerInput, ContextOutcomeRead, EUAIActTier } from "@irontrust/api-client";
import {
  useClassificationContext,
  useMe,
  usePreviewContext,
  useSubmitContext,
} from "@/lib/intake";

const OVERRIDE_TIER_OPTIONS: SelectOption[] = [
  { value: "high_risk", label: "High risk" },
  { value: "limited_risk", label: "Limited risk" },
  { value: "minimal_risk", label: "Minimal risk" },
];

export interface ContextGateStepProps {
  useCaseId: string;
  onResolved: () => void;
  onProhibitedHalt: () => void;
}

/**
 * WI-8: the context-question gate (only rendered when WI-7's create
 * response carries requires_context). Preview-before-commit (UX-4/D-1):
 * every submit is preceded by a preview; an UNRESOLVED preview re-prompts
 * for the missing questions and issues no write (the loop). `override_tier`
 * is system_owner-only (FE-8, structural bar via SodAction) — a bare
 * contributor must never see it.
 */
export function ContextGateStep({ useCaseId, onResolved, onProhibitedHalt }: ContextGateStepProps) {
  const context = useClassificationContext(useCaseId);
  const me = useMe();
  const preview = usePreviewContext(useCaseId);
  const submit = useSubmitContext(useCaseId);

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [outcome, setOutcome] = useState<ContextOutcomeRead | null>(null);
  const [overrideTier, setOverrideTier] = useState<EUAIActTier | "">("");
  const [justification, setJustification] = useState("");

  const isSystemOwner = me.data?.governance_roles.some((r) => r.key === "system_owner") ?? false;

  if (context.isLoading) return <p>Loading questions…</p>;
  if (context.isError || !context.data) return <p role="alert">Could not load the classification questions.</p>;

  const { tree_version, questions } = context.data.residual_questions;

  function buildAnswerInputs(): AnswerInput[] {
    return Object.entries(answers)
      .filter(([, optionCode]) => optionCode)
      .map(([question_code, option_code]) => ({ question_code, option_code }));
  }

  function handlePreview(e: FormEvent) {
    e.preventDefault();
    preview.mutate(
      { answers: buildAnswerInputs(), tree_version },
      { onSuccess: setOutcome }
    );
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submit.mutate(
      {
        answers: buildAnswerInputs(),
        tree_version,
        override_tier: isSystemOwner && overrideTier ? overrideTier : null,
        justification: isSystemOwner && overrideTier ? justification || null : null,
      },
      {
        onSuccess: (data) => {
          if (data.outcome.kind === "PROHIBITED_HALT") {
            onProhibitedHalt();
          } else {
            onResolved();
          }
        },
      }
    );
  }

  return (
    <section aria-label="context-gate">
      <form aria-label="context-questions" onSubmit={handlePreview}>
        {questions.map((q) => (
          <div key={q.code}>
            <SingleSelect
              id={`question-${q.code}`}
              label={q.text}
              value={answers[q.code] ?? ""}
              options={q.options.map((o) => ({ value: o.code, label: o.label }))}
              onChange={(v) => setAnswers((prev) => ({ ...prev, [q.code]: v }))}
            />
            {q.legal_ref && <p className="text-text-muted text-sm">{q.legal_ref}</p>}
            {outcome?.kind === "UNRESOLVED" && outcome.missing.includes(q.code) && (
              <p role="alert">This answer is still needed.</p>
            )}
          </div>
        ))}

        <Button type="submit" variant="secondary" disabled={preview.isPending}>
          Preview outcome
        </Button>
      </form>

      {outcome && (
        <div aria-label="outcome-preview">
          <p>{outcome.rationale}</p>
          {outcome.kind === "UNRESOLVED" ? (
            <p>More answers are needed before this can be submitted.</p>
          ) : (
            <form aria-label="context-submit" onSubmit={handleSubmit}>
              <p>
                Resolved tier: {outcome.tier} ({outcome.kind})
              </p>

              <SodAction barred={!isSystemOwner}>
                <fieldset>
                  <legend>Override (optional)</legend>
                  <SingleSelect
                    id="context-override-tier"
                    label="Override tier"
                    value={overrideTier}
                    options={OVERRIDE_TIER_OPTIONS}
                    onChange={(v) => setOverrideTier(v as EUAIActTier)}
                  />
                  <FreeText
                    id="context-override-justification"
                    label="Justification (optional)"
                    value={justification}
                    onChange={setJustification}
                  />
                </fieldset>
              </SodAction>

              {submit.isError && <p role="alert">Could not submit. Try again.</p>}

              <Button type="submit" disabled={submit.isPending}>
                Submit
              </Button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
