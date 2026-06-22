"use client";

/**
 * UI-F3-ASSESS / UI-F4-ASSURE — use-case work surface.
 *
 * F3 §0 pre-flight outcomes (resolved against live code, D-21):
 *   V-1a PENDING_REVIEW: bridge snapshot status is PENDING_REVIEW — no path assumed APPROVED.
 *   V-1b B1 does NOT invert: create_aiia guard uses classification_readiness(), which
 *        does NOT require snapshot status=APPROVED; only requires eu_tier ≠
 *        REQUIRES_CONTEXT/UNCLASSIFIED. F3 bootstraps without F4 sign-off.
 *   V-2  AssessmentDetail: lock_version in body; source_assessment_id for feeder surfacing.
 *   V-3  Five If-Match routes confirmed: PATCH items, confirm, submit, review, reopen.
 *   V-5  ProvenanceConfidence is 5-value (user_provided added to enum mirror).
 *   V-6  FeederRecommendationRead: {type, applicability, basis, exists}.
 *   V-7  Gates: bootstrap/submit = gov:system_owner; items = gov:write.
 *   V-8  Required feeders DO gate structural_assessment_readiness (park on
 *        "required_feeder_missing") — A7's provisional defer is a scope hole for
 *        feeder-gated tiers. Submit UI is correct; gate is server-enforced.
 *   V-4  F2 system drill-in had no forward link — patched in system-detail-client.tsx.
 *   Backend additive delta: control_links added to AssessmentItemRead + batch-loaded
 *        in assemble_aiia_items (UI-F3-ASSESS; not captured in "backend delta none"
 *        which referred to routes/tables/enums, not response schema fields).
 *
 * F4 §0 pre-flight outcomes:
 *   V-1  list_review_queue pre-filters submitted_by_user_id != ctx.user_id.
 *        ReviewQueueEntryRead = {assessment_id, use_case_id, tier_snapshot,
 *        submitted_by_name, submitted_by_email, submitted_at}. No caller_eligible.
 *        WI-9a NOT elected; across-reassignment edge → act-time 403.
 *   V-2  AssessmentDetail has no review history. WI-9b elected: additive reviews[]
 *        field added to AssessmentDetail (reviewer_display_name from INV-34 join).
 *   V-3  AuthoriseRequest = {residual_risk_statement: str}.
 *        DeploymentAuthorisationRead includes live_state (INV-32).
 *   V-4  ReviewDecision = "approved" | "changes_requested". note required (422) on
 *        changes_requested, optional on approved.
 *   V-6  SignOffRead shape confirmed; no If-Match on sign-off route; 409/403 only.
 */

import { useMe, useUseCaseLifecycle } from "@/lib/assess";
import { useAssessments, useUseCaseDetail } from "@/lib/assess";
import { isYourCourt, resolveCourt, useSystemRollup } from "@/lib/portfolio";
import { AssessmentHeader } from "./_regions/assessment-header";
import { AiiaBody } from "./_regions/aiia-body";
import { FeederRecs } from "./_regions/feeder-recs";
import { ReviewPanel } from "./_regions/review-panel";
import { SignOffPanel } from "./_regions/sign-off-panel";
import { AuthorisePanel } from "./_regions/authorise-panel";
import { AtoTerminal } from "./_regions/ato-terminal";
import { ReviewHistory } from "./_regions/review-history";
import { AuditPanels } from "./_regions/audit-panels";
import {
  useBootstrapAssessment,
  useSubmitAssessment,
  useReopen,
  StaleLockError,
  BadFromStateError,
} from "@/lib/assess";
import { SodAction, StaleLockBanner, BadFromStateBanner } from "@irontrust/ui";
import { useState } from "react";
import type { ClassificationStatusRead } from "@irontrust/api-client";

interface Props {
  useCaseId: string;
}

export type RoleBranch =
  | "system_owner"
  | "contributor"
  | "reviewer"
  | "authoriser"
  | "auditor";

/**
 * Resolve the five-way role branch from the caller's governance roles (UI-F4-ASSURE).
 * Admin = zero governance roles. system_owner/contributor are exclusive first-line roles.
 * Assurance roles are split so each gets its own act surface (DF4-1).
 * Priority: system_owner > contributor > reviewer > authoriser > auditor.
 */
export function resolveRoleBranch(roleKeys: Set<string>): "admin" | RoleBranch {
  if (roleKeys.size === 0) return "admin";
  if (roleKeys.has("system_owner")) return "system_owner";
  if (roleKeys.has("contributor")) return "contributor";
  if (roleKeys.has("reviewer")) return "reviewer";
  if (roleKeys.has("authoriser")) return "authoriser";
  return "auditor";
}

export function AssessmentPageClient({ useCaseId }: Props) {
  const me = useMe();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));
  const branch = resolveRoleBranch(roleKeys);

  // Admin gets an empty state; no gov:ALL call issued (DF2-5).
  if (branch === "admin") {
    return (
      <section aria-label="admin-empty-state">
        <h1>Use Case Assessment</h1>
        <p>
          Your account doesn&apos;t hold a governance role, so the assessment is not accessible.
          Contact a tenant admin to be assigned a governance role.
        </p>
      </section>
    );
  }

  return (
    <AssessmentSurface
      useCaseId={useCaseId}
      roleKeys={roleKeys}
      branch={branch}
    />
  );
}

function AssessmentSurface({
  useCaseId,
  roleKeys,
  branch,
}: {
  useCaseId: string;
  roleKeys: Set<string>;
  branch: RoleBranch;
}) {
  const useCaseDetail = useUseCaseDetail(useCaseId);
  const lifecycle = useUseCaseLifecycle(useCaseId);
  const assessmentsQuery = useAssessments(useCaseId);
  const rollup = useSystemRollup(
    useCaseDetail.data?.use_case.system_id ?? ""
  );

  if (
    useCaseDetail.isLoading ||
    lifecycle.isLoading ||
    assessmentsQuery.isLoading ||
    rollup.isLoading
  ) {
    return <p>Loading assessment…</p>;
  }

  if (
    useCaseDetail.isError ||
    !useCaseDetail.data ||
    lifecycle.isError ||
    !lifecycle.data ||
    assessmentsQuery.isError
  ) {
    return <p role="alert">Could not load the assessment.</p>;
  }

  const useCase = useCaseDetail.data.use_case;
  const classification = useCaseDetail.data.classification ?? null;
  const lifecycleState = lifecycle.data.state;
  const court = resolveCourt(lifecycle.data.blocking);
  const aiia = (assessmentsQuery.data ?? []).find((a) => a.type === "aiia" && a.is_current) ?? null;

  return (
    <main>
      <AssessmentHeader
        useCaseId={useCaseId}
        useCaseTitle={useCase.title}
        euTier={useCase.eu_tier}
        systemName={rollup.data?.system_name ?? null}
        court={court}
        roleKeys={roleKeys}
        branch={branch}
      />

      {/* ATO terminal: shown to any gov role when use case is authorised (INV-32, WI-5) */}
      {lifecycleState === "authorised" && (
        <AtoTerminal useCaseId={useCaseId} />
      )}

      {/* Audit panels: coverage + export + ATO document (UI-F6-AUDITPACK). */}
      <AuditPanels
        useCaseId={useCaseId}
        assessmentId={aiia?.id ?? null}
        assessmentStatus={aiia?.status ?? null}
        canView={true}
      />

      {aiia === null ? (
        <NoAssessmentState useCaseId={useCaseId} branch={branch} classification={classification} />
      ) : (
        <>
          <AiiaBody
            assessmentId={aiia.id}
            assessmentStatus={aiia.status}
            branch={branch}
          />
          <FeederRecs assessmentId={aiia.id} />

          {/* Reviewer act panels — mutually exclusive by object state (DF4-2) */}
          {branch === "reviewer" && aiia.status === "in_review" && (
            <ReviewPanel
              useCaseId={useCaseId}
              assessmentId={aiia.id}
              assessmentLockVersion={aiia.lock_version}
            />
          )}
          {branch === "reviewer" && classification?.status === "pending_review" && (
            <SignOffPanel
              useCaseId={useCaseId}
              classification={classification}
            />
          )}

          {/* Authoriser act panel */}
          {branch === "authoriser" && lifecycleState === "pending_authorisation" && (
            <AuthorisePanel useCaseId={useCaseId} />
          )}

          {/* Submit — system_owner only, DRAFT/NEEDS_REFRESH only (WI-6 / F3) */}
          <SubmitSection
            useCaseId={useCaseId}
            assessmentId={aiia.id}
            assessmentStatus={aiia.status}
            assessmentLockVersion={aiia.lock_version}
            branch={branch}
          />

          {/* Reopen — system_owner only, APPROVED only (WI-6 / F4) */}
          <ReopenSection
            useCaseId={useCaseId}
            assessmentId={aiia.id}
            assessmentStatus={aiia.status}
            assessmentLockVersion={aiia.lock_version}
            branch={branch}
          />

          {/* Review history — visible to owner, reviewer, authoriser (WI-7) */}
          {(branch === "system_owner" || branch === "reviewer" || branch === "authoriser") && (
            <ReviewHistory assessmentId={aiia.id} />
          )}
        </>
      )}
    </main>
  );
}

function SubmitSection({
  useCaseId,
  assessmentId,
  assessmentStatus,
  assessmentLockVersion,
  branch,
}: {
  useCaseId: string;
  assessmentId: string;
  assessmentStatus: string;
  assessmentLockVersion: number;
  branch: RoleBranch;
}) {
  const [submitError, setSubmitError] = useState<"stale" | "bad_state" | null>(null);
  const submit = useSubmitAssessment(useCaseId, assessmentId);
  const isSystemOwner = branch === "system_owner";
  const canSubmit = assessmentStatus === "draft" || assessmentStatus === "needs_refresh";

  if (!canSubmit) return null;

  return (
    <section aria-label="submit-section">
      {submitError === "stale" && (
        <StaleLockBanner onReload={() => setSubmitError(null)} />
      )}
      {submitError === "bad_state" && <BadFromStateBanner />}

      {/* Submit is structurally absent for non-system_owner (FE-8) */}
      <SodAction barred={!isSystemOwner}>
        <button
          onClick={() => {
            setSubmitError(null);
            submit.mutate(assessmentLockVersion, {
              onError: (err) => {
                if (err instanceof StaleLockError) setSubmitError("stale");
                else if (err instanceof BadFromStateError) setSubmitError("bad_state");
              },
            });
          }}
          disabled={submit.isPending}
          aria-busy={submit.isPending}
        >
          {submit.isPending ? "Submitting…" : "Submit for review"}
        </button>
      </SodAction>
    </section>
  );
}

/**
 * Reopen control (WI-6 / F4) — system_owner only, APPROVED AIIA only.
 * APPROVED → NEEDS_REFRESH; authoring fields unlock on refetch.
 * Sends If-Match (FE-6); 412 ≠ 409 surfaced distinctly.
 */
function ReopenSection({
  useCaseId,
  assessmentId,
  assessmentStatus,
  assessmentLockVersion,
  branch,
}: {
  useCaseId: string;
  assessmentId: string;
  assessmentStatus: string;
  assessmentLockVersion: number;
  branch: RoleBranch;
}) {
  const [reopenError, setReopenError] = useState<"stale" | "bad_state" | null>(null);
  const reopen = useReopen(useCaseId, assessmentId);

  if (branch !== "system_owner" || assessmentStatus !== "approved") return null;

  return (
    <section aria-label="reopen-section">
      {reopenError === "stale" && (
        <StaleLockBanner onReload={() => setReopenError(null)} />
      )}
      {reopenError === "bad_state" && <BadFromStateBanner />}

      <button
        onClick={() => {
          setReopenError(null);
          reopen.mutate(assessmentLockVersion, {
            onError: (err) => {
              if (err instanceof StaleLockError) setReopenError("stale");
              else if (err instanceof BadFromStateError) setReopenError("bad_state");
            },
          });
        }}
        disabled={reopen.isPending}
        aria-busy={reopen.isPending}
      >
        {reopen.isPending ? "Reopening…" : "Reopen for revision"}
      </button>
    </section>
  );
}

function NoAssessmentState({
  useCaseId,
  branch,
  classification,
}: {
  useCaseId: string;
  branch: RoleBranch;
  classification: ClassificationStatusRead | null;
}) {
  const bootstrap = useBootstrapAssessment(useCaseId);
  const [blockedReason, setBlockedReason] = useState<string | null>(null);

  if (branch === "contributor") {
    return (
      <section aria-label="assessment-empty-state">
        <p>A system owner must start the assessment for this use case.</p>
      </section>
    );
  }

  if (branch === "reviewer") {
    // Reviewer may have a classification sign-off pending even without an AIIA
    if (classification?.status === "pending_review") {
      return (
        <SignOffPanel useCaseId={useCaseId} classification={classification} />
      );
    }
    return (
      <section aria-label="assessment-empty-state">
        <p>No assessment has been started for this use case yet.</p>
      </section>
    );
  }

  if (branch === "authoriser" || branch === "auditor") {
    return (
      <section aria-label="assessment-empty-state">
        <p>No assessment has been started for this use case yet.</p>
      </section>
    );
  }

  // system_owner: show create control (or blocked reason from 409)
  return (
    <section aria-label="assessment-empty-state">
      {blockedReason ? (
        <p role="alert">{blockedReason}</p>
      ) : (
        <>
          <p>No assessment has been started for this use case.</p>
          <button
            onClick={() =>
              bootstrap.mutate(undefined, {
                onError: (err) => {
                  if (err instanceof BadFromStateError) {
                    const body = (err as BadFromStateError).body as Record<string, unknown> | null;
                    const detail =
                      typeof body?.detail === "string"
                        ? body.detail
                        : "This use case cannot start an assessment in its current state.";
                    setBlockedReason(detail);
                  }
                },
              })
            }
            disabled={bootstrap.isPending}
            aria-busy={bootstrap.isPending}
          >
            {bootstrap.isPending ? "Starting…" : "Start assessment"}
          </button>
        </>
      )}
    </section>
  );
}
