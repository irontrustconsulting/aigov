/** app/schemas/lifecycle.py — the whose-court read (WI-9), the
 * portfolio/rollup read (UI-F2-PORTFOLIO), and the clearance-queue read
 * plus vendor/product approval act (UI-F10-CLEARANCE). */
import type { ApprovalStatus, EUAIActTier, LifecycleState } from "./enums";

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

// ---------------------------------------------------------------------------
// Vendor/product clearance (UI-F10-CLEARANCE) — PUT /vendors|products/{id}/
// approval (act) + GET /clearance-queue (read).
// ---------------------------------------------------------------------------

export interface VendorApprovalCreate {
  status: ApprovalStatus;
  valid_until?: string | null;
  note?: string | null;
}

export interface VendorApprovalRead {
  id: string;
  catalogue_vendor_id: string;
  status: ApprovalStatus;
  valid_until: string | null;
  decided_by_user_id: string | null;
  decided_at: string | null;
  note: string | null;
}

export interface ProductApprovalCreate {
  status: ApprovalStatus;
  valid_until?: string | null;
  note?: string | null;
}

export interface ProductApprovalRead {
  id: string;
  catalogue_product_id: string;
  status: ApprovalStatus;
  valid_until: string | null;
  decided_by_user_id: string | null;
  decided_at: string | null;
  note: string | null;
}

export interface ProductClearanceEntry {
  catalogue_product_id: string;
  product_name: string;
  status: ApprovalStatus;
  valid_until: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  note: string | null;
  vendor_cleared: boolean;
  awaiting_use_case_count: number;
  affected_use_case_count: number;
  affected_system_count: number;
}

export interface VendorClearanceEntry {
  catalogue_vendor_id: string;
  vendor_name: string;
  status: ApprovalStatus;
  valid_until: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  note: string | null;
  awaiting_use_case_count: number;
  affected_use_case_count: number;
  affected_system_count: number;
  products: ProductClearanceEntry[];
}

/** GET /v1/clearance-queue (gov:ALL read). Recomputed live — never cached
 * (same FE-7 posture as portfolio/system-rollup). */
export interface ClearanceQueueRead {
  vendors: VendorClearanceEntry[];
}
