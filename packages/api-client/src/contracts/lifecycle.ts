/** app/schemas/lifecycle.py — the whose-court read (WI-9) and the
 * portfolio/rollup read (UI-F2-PORTFOLIO). */
import type { EUAIActTier, LifecycleState } from "./enums";

export interface GateResultRead {
  state: LifecycleState;
  verdict: string;
  reason_code: string;
  reason: string;
  responsible_party: string;
}

export interface UseCaseLifecycleRead {
  use_case_id: string;
  state: LifecycleState;
  held_from_state: LifecycleState | null;
  held_reason: string | null;
  gates: GateResultRead[];
  blocking: GateResultRead | null;
}

export interface UseCaseRollupEntry {
  use_case_id: string;
  title: string;
  state: LifecycleState;
  eu_tier: EUAIActTier;
  blocking: GateResultRead | null;
}

/** GET /v1/portfolio (one entry per system, >=1 use case) and
 * GET /v1/systems/{id}/rollup (single entry) share this shape. */
export interface SystemRollupRead {
  system_id: string;
  system_name: string;
  use_case_count: number;
  highest_tier: EUAIActTier | null;
  use_cases: UseCaseRollupEntry[];
}
