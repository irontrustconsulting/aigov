"use client";

import { useState } from "react";
import { Dialog, Button, SingleSelect, ConstrainedDateInput, FreeText } from "@irontrust/ui";
import type { ApprovalStatus } from "@irontrust/api-client";
import { useSetProductApproval, useSetVendorApproval } from "@/lib/clearances";

export interface ClearanceTarget {
  kind: "vendor" | "product";
  id: string;
  name: string;
  status: ApprovalStatus;
  validUntil: string | null;
  note: string | null;
  affectedUseCaseCount: number;
  affectedSystemCount: number;
}

/** DF-CLR-18: only these three are settable from the surface — NOT_STARTED
 * has no act (it's the absence of a row) and EXPIRED is reserved for future
 * auto-expiry, never set by hand. */
const STATUS_OPTIONS = [
  { value: "under_review", label: "Under review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultValidUntil(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

export function ClearanceDialog({
  target,
  open,
  onClose,
}: {
  target: ClearanceTarget;
  open: boolean;
  onClose: () => void;
}) {
  const [stage, setStage] = useState<"form" | "confirm">("form");
  const [status, setStatus] = useState<string>(target.status === "not_started" ? "" : target.status);
  const [validUntil, setValidUntil] = useState<string>(target.validUntil?.slice(0, 10) ?? "");
  const [note, setNote] = useState<string>(target.note ?? "");
  const [dateError, setDateError] = useState<string | null>(null);

  const setVendorApproval = useSetVendorApproval(target.id);
  const setProductApproval = useSetProductApproval(target.id);
  const mutation = target.kind === "vendor" ? setVendorApproval : setProductApproval;

  function handleStatusChange(value: string) {
    setStatus(value);
    // Client-side opinionated default (UX-3): prefill one year out on
    // APPROVED when no date is set yet. Never overwrites an existing value.
    if (value === "approved" && !validUntil) {
      setValidUntil(defaultValidUntil());
    }
  }

  function handleReview(e: React.FormEvent) {
    e.preventDefault();
    if (validUntil && validUntil < todayIso()) {
      setDateError("Choose a date in the future.");
      return;
    }
    setDateError(null);
    setStage("confirm");
  }

  function handleConfirm() {
    mutation.mutate(
      {
        status: status as ApprovalStatus,
        valid_until: validUntil ? new Date(validUntil).toISOString() : null,
        note: note.trim() || null,
      },
      { onSuccess: onClose }
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Set clearance — ${target.name}`}
    >
      <div className="mt-4 min-w-80 space-y-4">
        {stage === "form" && (
          <form onSubmit={handleReview} className="space-y-4">
            <SingleSelect
              id="clearance-status"
              label="Status"
              value={status}
              options={STATUS_OPTIONS}
              onChange={handleStatusChange}
            />
            <ConstrainedDateInput
              id="clearance-valid-until"
              label="Valid until (optional)"
              value={validUntil}
              onChange={setValidUntil}
            />
            <p className="text-ink-muted text-xs">
              An expired date re-blocks affected use cases at this gate until cleared again.
            </p>
            {dateError && (
              <p className="text-danger text-sm" role="alert">{dateError}</p>
            )}
            <FreeText id="clearance-note" label="Note" value={note} onChange={setNote} />
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={!status}>
                Review
              </Button>
            </div>
          </form>
        )}

        {stage === "confirm" && (
          <div className="space-y-4">
            <p className="text-sm text-ink">
              Setting {target.name} to{" "}
              <span className="font-medium">
                {STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status}
              </span>{" "}
              will re-evaluate {target.affectedUseCaseCount} use case
              {target.affectedUseCaseCount === 1 ? "" : "s"} across {target.affectedSystemCount} system
              {target.affectedSystemCount === 1 ? "" : "s"}.
            </p>
            {mutation.isError && (
              <p className="text-danger text-sm" role="alert">
                Could not set clearance. Try again.
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setStage("form")}>
                Back
              </Button>
              <Button type="button" onClick={handleConfirm} disabled={mutation.isPending}>
                {mutation.isPending ? "Setting…" : "Confirm"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}
