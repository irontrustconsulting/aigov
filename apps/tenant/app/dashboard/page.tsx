"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useMe, useActiveDraft } from "@/lib/intake";
import { courtHref, isYourCourt, resolveCourt, useSystems, usePortfolio } from "@/lib/portfolio";
import {
  WhoseCourtIndicator,
  VerdictChip,
  TierBadge,
  toTierMember,
  PageScaffold,
  PageHeader,
  StatCard,
  SectionHeader,
  SectionGroup,
  DataTable,
  DataTableHeader,
  DataTableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  EmptyState,
  Skeleton,
  ErrorState,
  DraftResumeIndicator,
} from "@irontrust/ui";
import type { SystemRollupRead } from "@irontrust/api-client";

// 1st-line roles lead with your-court; 2nd/3rd-line (assurance face) lead
// with portfolio posture instead (UX-5, D-24: from the server-authoritative
// role set, never a token claim) — both sections render for either face.
const ADOPTION_ROLE_KEYS = new Set(["system_owner", "contributor"]);

/**
 * UI-C1-PORTFOLIO-IDENTITY: F2 portfolio composition pass.
 * Preserves all F2 semantic contracts (DF2-5, DF6-9, FE-11, INV-52);
 * composes from the C0 kit (FE-20..23, INV-69, INV-70).
 */
export default function DashboardPage() {
  const me = useMe();

  if (me.isLoading) {
    return (
      <PageScaffold>
        <Skeleton lines={5} />
      </PageScaffold>
    );
  }

  if (me.isError || !me.data) {
    return (
      <PageScaffold>
        <ErrorState
          message="Could not load your role."
          onRetry={() => me.refetch()}
        />
      </PageScaffold>
    );
  }

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));

  if (roleKeys.size === 0) {
    // DF2-5: admin branch — no portfolio call issued.
    return (
      <PageScaffold>
        <section aria-label="admin-empty-state">
          <PageHeader title="Portfolio" />
          <EmptyState message="Your account doesn't hold a governance role yet, so there's no portfolio to show. Once a governance role is assigned, systems and use cases you're party to will appear here." />
        </section>
      </PageScaffold>
    );
  }

  return <PortfolioHub roleKeys={roleKeys} />;
}

function resolveLabel(blob: Record<string, unknown>): string | null {
  const label =
    (blob.catalogueProductName as string | undefined) ??
    (blob.name as string | undefined) ??
    null;
  return typeof label === "string" ? label : null;
}

function PortfolioHub({ roleKeys }: { roleKeys: Set<string> }) {
  const portfolio = usePortfolio();
  const systems = useSystems();
  const activeDraft = useActiveDraft({ enabled: roleKeys.has("system_owner") });

  if (portfolio.isLoading || systems.isLoading) {
    return (
      <PageScaffold>
        <Skeleton lines={8} />
      </PageScaffold>
    );
  }

  if (portfolio.isError || !portfolio.data || systems.isError || !systems.data) {
    return (
      <PageScaffold>
        <ErrorState
          message="Could not load the portfolio."
          onRetry={() => {
            portfolio.refetch();
            systems.refetch();
          }}
        />
      </PageScaffold>
    );
  }

  const isAdoptionFace = [...roleKeys].some((k) => ADOPTION_ROLE_KEYS.has(k));

  const draftBanner =
    activeDraft.data != null ? (
      <DraftResumeIndicator
        productLabel={resolveLabel(activeDraft.data.draft_blob)}
        href="/systems/new"
      />
    ) : null;

  const zeroUseCaseSystems = systems.data.filter(
    (s) => !portfolio.data!.some((p) => p.system_id === s.id)
  );

  const yourCourtEntries = portfolio.data.flatMap((system) =>
    system.use_cases
      .map((useCase) => ({ system, useCase, court: resolveCourt(useCase.blocking) }))
      .filter(({ court }) => isYourCourt(court, roleKeys))
  );

  // Stat derivation — client-side from existing reads; no new API calls (DF6-9).
  const systemCount = systems.data.length;
  const useCaseCount = portfolio.data.reduce((n, s) => n + s.use_cases.length, 0);
  const awaitingYouCount = yourCourtEntries.length;

  if (systemCount === 0 && portfolio.data.length === 0) {
    // D-61: zero-systems renders scaffolded-empty (supersedes UI-C1 FirstRunPanel takeover).
    // INV-74: retained chrome (header + stat row + framed table); get-started content is in-region.
    return (
      <PageScaffold>
        {draftBanner}
        <PageHeader
          title="Portfolio"
          action={
            roleKeys.has("system_owner") ? (
              <Link
                href="/systems/new"
                className="inline-flex items-center justify-center rounded-md border border-transparent bg-brand px-4 py-2 text-sm font-medium text-surface"
              >
                Register a system
              </Link>
            ) : undefined
          }
        />
        <div className="grid grid-cols-3 gap-4" role="region" aria-label="stats">
          <StatCard label="Systems" value={0} />
          <StatCard label="Use cases under governance" value={0} />
          <StatCard label="Awaiting you" value={0} />
        </div>
        <section aria-label="systems">
          <SectionHeader title="Systems" />
          <div className="mt-3">
            <DataTable>
              <DataTableHeader>
                <TableHeaderCell>System / Use case</TableHeaderCell>
                <TableHeaderCell>Tier</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Court</TableHeaderCell>
              </DataTableHeader>
              <DataTableBody emptyMessage="No systems registered yet." />
            </DataTable>
          </div>
        </section>
      </PageScaffold>
    );
  }

  const yourCourtSection = (
    <section aria-label="your-court">
      <SectionHeader title="Your court" />
      <div className="mt-3">
        {yourCourtEntries.length === 0 ? (
          <EmptyState message="Nothing is waiting on you right now." />
        ) : (
          <ul className="space-y-2">
            {yourCourtEntries.map(({ system, useCase, court }) => {
              const href = courtHref(court, useCase.use_case_id);
              return (
                <li key={useCase.use_case_id}>
                  <Link
                    href={href}
                    className="block rounded-lg border border-hairline bg-paper p-4 transition-colors hover:bg-surface-sunken"
                    style={{ boxShadow: "var(--elevation-raised)" }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {court && (
                            <WhoseCourtIndicator partyLabel={court.partyLabel} isYourCourt />
                          )}
                          <VerdictChip value={useCase.state} />
                          <span className="truncate text-sm font-medium">{system.system_name}</span>
                          <span className="text-ink-muted">·</span>
                          <span className="truncate text-sm text-ink-muted">{useCase.title}</span>
                        </div>
                        {court?.reason && (
                          <p className="text-xs text-ink-muted">{court.reason}</p>
                        )}
                      </div>
                      <ChevronRight className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );

  // Client-side tally of use_cases[].state, already loaded with the
  // portfolio read — no new API call (DF6-9). Counts only, no percentage
  // (INV-52). Most-prevalent state first.
  const stateCounts = new Map<string, number>();
  for (const system of portfolio.data) {
    for (const useCase of system.use_cases) {
      stateCounts.set(useCase.state, (stateCounts.get(useCase.state) ?? 0) + 1);
    }
  }
  const stateDistribution = [...stateCounts.entries()].sort((a, b) => b[1] - a[1]);

  const postureSection = (
    <section aria-label="portfolio-posture">
      <SectionGroup title="Portfolio posture">
        <div className="space-y-3">
          <p className="text-sm text-ink-muted">
            {portfolio.data.length} system{portfolio.data.length === 1 ? "" : "s"} with at least one
            use case under governance.
          </p>
          <div
            className="flex flex-wrap items-center gap-3"
            role="list"
            aria-label="lifecycle-state distribution"
          >
            {stateDistribution.map(([state, count]) => (
              <span key={state} role="listitem" className="inline-flex items-center gap-1.5 text-sm">
                <span className="font-medium">{count}</span>
                <VerdictChip value={state} />
              </span>
            ))}
          </div>
          {/* Navigation only — no coverage truth rendered here (DF6-9). */}
          <Link
            href="/audit"
            className="inline-flex items-center gap-1 rounded-md border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-sunken"
          >
            View control coverage and audit packs →
          </Link>
        </div>
      </SectionGroup>
    </section>
  );

  // All use-case rows for the systems table.
  const systemRows = [
    ...portfolio.data.flatMap((system) =>
      system.use_cases.map((useCase) => ({
        kind: "usecase" as const,
        system,
        useCase,
        court: resolveCourt(useCase.blocking),
      }))
    ),
    ...zeroUseCaseSystems.map((s) => ({
      kind: "zero" as const,
      system: s,
    })),
  ];

  return (
    <PageScaffold>
      {draftBanner}
      <PageHeader
        title="Portfolio"
        action={
          roleKeys.has("system_owner") ? (
            <Link
              href="/systems/new"
              className="inline-flex items-center justify-center rounded-md border border-transparent bg-brand px-4 py-2 text-sm font-medium text-surface"
            >
              Register a system
            </Link>
          ) : undefined
        }
      />

      {/* Stat row — 3 lifecycle counts; no coverage, no % (DF6-9, INV-52) */}
      <div className="grid grid-cols-3 gap-4" role="region" aria-label="stats">
        <StatCard label="Systems" value={systemCount} />
        <StatCard label="Use cases under governance" value={useCaseCount} />
        <StatCard label="Awaiting you" value={awaitingYouCount} />
      </div>

      {/* Face-order (FE-11): adoption leads with your-court; assurance leads with posture */}
      {isAdoptionFace ? (
        <>
          {yourCourtSection}
          {postureSection}
        </>
      ) : (
        <>
          {postureSection}
          {yourCourtSection}
        </>
      )}

      <section aria-label="systems">
        <SectionHeader title="Systems" />
        <div className="mt-3">
          <DataTable>
            <DataTableHeader>
              <TableHeaderCell>System / Use case</TableHeaderCell>
              <TableHeaderCell>Tier</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Court</TableHeaderCell>
            </DataTableHeader>
            <DataTableBody emptyMessage="No systems registered yet.">
              {systemRows.map((row, i) => {
                if (row.kind === "zero") {
                  return (
                    <TableRow key={`zero-${i}`}>
                      <td colSpan={4} className="px-4 py-3" aria-label="zero-use-case-system">
                        <p className="font-medium text-sm">{row.system.name}</p>
                        <p className="text-xs text-ink-muted">No use case registered yet for this system.</p>
                      </td>
                    </TableRow>
                  );
                }
                const { system, useCase, court } = row;
                return (
                  <TableRow key={useCase.use_case_id}>
                    <TableCell>
                      <Link
                        href={`/systems/${system.system_id}`}
                        className="font-medium underline"
                      >
                        {system.system_name}
                      </Link>
                      <span className="mx-1 text-ink-muted">·</span>
                      <Link
                        href={`/use-cases/${useCase.use_case_id}`}
                        className="text-ink-muted underline"
                      >
                        {useCase.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {useCase.eu_tier ? (
                        <TierBadge value={toTierMember(useCase.eu_tier)} variant="compact" />
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <VerdictChip value={useCase.state} />
                    </TableCell>
                    <TableCell>
                      {court && (
                        <WhoseCourtIndicator
                          partyLabel={court.partyLabel}
                          isYourCourt={isYourCourt(court, roleKeys)}
                        />
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </DataTableBody>
          </DataTable>
        </div>
      </section>
    </PageScaffold>
  );
}
