/** app/schemas/classification.py — the context-question gate (gate 2). */
import type { ClassificationStatusRead } from "./classification";
import type { EUAIActTier, ProvenanceConfidence } from "./enums";

/** app/schemas/classification.py AnswerIn — `provenance` defaults
 * server-side to USER_CONFIRMED. The client never authors it (FE-9,
 * INV-13; the `assertNoForbiddenFields` runtime guard would reject it if
 * sent) — `AnswerInput` below is what the client actually constructs. */
export interface AnswerIn {
  question_code: string;
  option_code: string;
  provenance: ProvenanceConfidence;
}

export type AnswerInput = Omit<AnswerIn, "provenance">;

export interface OptionRead {
  code: string;
  label: string;
}

export interface QuestionRead {
  code: string;
  text: string;
  legal_ref: string | null;
  sort_order: number;
  options: OptionRead[];
}

export interface QuestionSetRead {
  tree_version: string;
  questions: QuestionRead[];
}

export interface ContextOutcomeRead {
  kind: "UNRESOLVED" | "RESOLVED" | "PROHIBITED_HALT";
  tier: EUAIActTier | null;
  subcategory_code: string | null;
  rationale: string;
  missing: string[];
}

export interface ClassificationContextRead {
  current_classification: ClassificationStatusRead | null;
  residual_questions: QuestionSetRead;
}

export interface ComputeRequest {
  answers: AnswerInput[];
  tree_version: string;
  override_tier: EUAIActTier | null;
  justification: string | null;
}

export interface PreviewRequest {
  answers: AnswerInput[];
  tree_version: string;
}

export interface ComputeResultRead {
  outcome: ContextOutcomeRead;
  classification: ClassificationStatusRead | null;
}
