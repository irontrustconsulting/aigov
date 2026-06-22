"use client";

/**
 * UI-F3-ASSESS — use-case work surface.
 *
 * §0 pre-flight outcomes (resolved against live code, D-21):
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
 */

import { useMe, useUseCaseLifecycle } from "@/lib/assess";
import { useAssessments, useUseCaseDetail } from "@/lib/assess";
import { isYourCourt, resolveCourt, useSystemRollup } from "@/lib/portfolio";
import { AssessmentHeader } from "./_regions/assessment-header";
import { AiiaBody } from "./_regions/aiia-body";
import { FeederRecs } from "./_regions/feeder-recs";
import { useBootstrapAssessment, useSubmitAssessment, StaleLockError, BadFromStateError } from "@/lib/assess";
import { SodAction, StaleLockBanner, BadFromStateBanner } from "@irontrust/ui";
import { useState } from "react";

interface Props {
  useCaseId: string;
}

/** Resolve the four-way role branch from the caller's governance roles.
 * Admin = zero governance roles. System_owner and contributor are exclusive
 * (a user can hold only one first-line role at a time per the SoD matrix).
 * Assurance roles (reviewer/authoriser/auditor) may coexist with each other. */
function resolveRoleBranch(roleKeys: Set<string>) {
  if (roleKeys.size === 0) return "admin" as const;
  if (roleKeys.has("system_owner")) return "system_owner" as const;
  if (roleKeys.has("contributor")) return "contributor" as const;
  return "assurance" as const; // reviewer | authoriser | auditor
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
  branch: "system_owner" | "contributor" | "assurance";
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

      {aiia === null ? (
        <NoAssessmentState useCaseId={useCaseId} branch={branch} />
      ) : (
        <>
          <AiiaBody
            assessmentId={aiia.id}
            assessmentStatus={aiia.status}
            branch={branch}
          />
          <FeederRecs assessmentId={aiia.id} />
          <SubmitSection
            useCaseId={useCaseId}
            assessmentId={aiia.id}
            assessmentStatus={aiia.status}
            assessmentLockVersion={aiia.lock_version}
            branch={branch}
          />
        </>
      )}
    </main>
  );
}

/**
 * Submit section (WI-6) — system_owner only (FE-8 structural: absent for contributor).
 * Sends If-Match on assessment.lock_version (FE-6/PAT-6).
 * Post-submit: body locked (IN_REVIEW), court moves to reviewer (lifecycle invalidated).
 * V-8 note: required feeders gate structural_assessment_readiness server-side; the 409
 * "bad from-state" surface handles any server rejection gracefully.
 */
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
  branch: "system_owner" | "contributor" | "assurance";
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

      {/* Submit is structurally absent for contributor (FE-8) */}
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

function NoAssessmentState({
  useCaseId,
  branch,
}: {
  useCaseId: string;
  branch: "system_owner" | "contributor" | "assurance";
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

  if (branch === "assurance") {
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
