/** app/schemas/lifecycle.py — the whose-court read (WI-9). */
import type { LifecycleState } from "./enums";

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
