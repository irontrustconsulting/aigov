"use client";

import Link from "next/link";
import { useMe } from "@/lib/intake";
import { isYourCourt, resolveCourt, useSystems, usePortfolio } from "@/lib/portfolio";
import { WhoseCourtIndicator, VerdictChip, TierBadge, toTierMember } from "@irontrust/ui";
import type { SystemRollupRead } from "@irontrust/api-client";

// 1st-line roles lead with your-court; 2nd/3rd-line (assurance face) lead
// with portfolio posture instead (UX-5, D-24: from the server-authoritative
// role set, never a token claim) — both sections render for either face.
const ADOPTION_ROLE_KEYS = new Set(["system_owner", "contributor"]);

/**
 * UI-F2-PORTFOLIO: the tenant portfolio landing — realises the F0
 * authenticated-landing route (`/dashboard`) as the navigational hub,
 * replacing the W7a/b smoke surface. Pure wire-up over `GET /v1/portfolio`,
 * `GET /v1/systems`, `GET /v1/me`; read-only (`re-evaluate` deferred, A1).
 *
 * `useMe()` fetches first and branches proactively (DF2-5): an admin-only
 * caller (zero governance roles) never mounts `PortfolioHub`, so the
 * `gov:ALL`-gated `GET /portfolio` request is never issued — not
 * issue-then-catch.
 */
export default function DashboardPage() {
  const me = useMe();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));

  if (roleKeys.size === 0) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-8">
        <section aria-label="admin-empty-state">
          <h1 className="mb-4 text-2xl font-semibold">Portfolio</h1>
          <p className="text-ink-muted text-sm">
            Your account doesn&apos;t hold a governance role yet, so there&apos;s no portfolio to show.
            Once a governance role is assigned, systems and use cases you&apos;re party to will appear
            here.
          </p>
        </section>
      </main>
    );
  }

  return <PortfolioHub roleKeys={roleKeys} />;
}

function PortfolioHub({ roleKeys }: { roleKeys: Set<string> }) {
  const portfolio = usePortfolio();
  const systems = useSystems();

  if (portfolio.isLoading || systems.isLoading) return <p>Loading your portfolio…</p>;
  if (portfolio.isError || !portfolio.data || systems.isError || !systems.data) {
    return <p role="alert">Could not load the portfolio.</p>;
  }

  // Both faces share one surface (DF2-2): which section leads differs by
  // role, but every governance-role caller sees both — including a
  // 2nd/3rd-line caller, whose own your-court set may simply be empty.
  const isAdoptionFace = [...roleKeys].some((k) => ADOPTION_ROLE_KEYS.has(k));

  const zeroUseCaseSystems = systems.data.filter(
    (s) => !portfolio.data.some((p) => p.system_id === s.id)
  );

  const yourCourtEntries = portfolio.data.flatMap((system) =>
    system.use_cases
      .map((useCase) => ({ system, useCase, court: resolveCourt(useCase.blocking) }))
      .filter(({ court }) => isYourCourt(court, roleKeys))
  );

  const yourCourtSection = (
    <section
      aria-label="your-court"
      className="rounded-lg px-4 py-3"
      style={{ background: "var(--court-yours-fill)", borderLeft: "3px solid var(--court-yours-bar)" }}
    >
      <h2 className="mb-2 font-semibold" style={{ color: "var(--court-yours-text)" }}>
        Your court
      </h2>
      {yourCourtEntries.length === 0 ? (
        <p className="text-ink-muted text-sm">Nothing is waiting on you right now.</p>
      ) : (
        <ul className="space-y-2">
          {yourCourtEntries.map(({ system, useCase, court }) => (
            <li key={useCase.use_case_id} className="flex flex-wrap items-center gap-2 text-sm">
              <Link href={`/systems/${system.system_id}`} className="font-medium underline">
                {system.system_name}
              </Link>
              <span className="text-ink-muted">—</span>
              <span>{useCase.title}: {court?.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );

  const postureSection = (
    <section aria-label="portfolio-posture" className="border-hairline rounded-lg border p-4">
      <h2 className="mb-2 font-semibold">Portfolio posture</h2>
      <p className="text-ink-muted text-sm">
        {portfolio.data.length} system{portfolio.data.length === 1 ? "" : "s"} with at least one use
        case under governance.
      </p>
      {/* Navigation only — no coverage truth rendered here (DF6-9). */}
      <Link href="/audit" className="mt-2 block text-sm underline">
        View control coverage and audit packs →
      </Link>
    </section>
  );

  return (
    <main className="mx-auto max-w-4xl space-y-8 px-6 py-8">
      <h1 className="text-2xl font-semibold">Portfolio</h1>

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
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Systems</h2>
          {roleKeys.has("system_owner") && (
            <Link href="/systems/new" className="text-sm underline">
              Register a system →
            </Link>
          )}
        </div>
        <ul className="space-y-3">
          {portfolio.data.map((system) => (
            <SystemCard key={system.system_id} system={system} roleKeys={roleKeys} />
          ))}
          {zeroUseCaseSystems.map((s) => (
            <li key={s.id} aria-label="zero-use-case-system" className="border-hairline rounded-lg border p-4">
              <p className="font-medium">{s.name}</p>
              <p className="text-ink-muted text-sm">No use case registered yet for this system.</p>
            </li>
          ))}
        </ul>
        {portfolio.data.length === 0 && zeroUseCaseSystems.length === 0 && (
          <p className="text-ink-muted text-sm">No systems registered yet.</p>
        )}
      </section>
    </main>
  );
}

function SystemCard({ system, roleKeys }: { system: SystemRollupRead; roleKeys: Set<string> }) {
  return (
    <li className="border-hairline rounded-lg border p-4">
      <Link href={`/systems/${system.system_id}`} className="font-semibold underline">
        {system.system_name}
      </Link>
      <ul className="mt-3 space-y-2">
        {system.use_cases.map((useCase) => {
          const court = resolveCourt(useCase.blocking);
          return (
            <li key={useCase.use_case_id} className="flex flex-wrap items-center gap-2 text-sm">
              <Link href={`/use-cases/${useCase.use_case_id}`} className="text-ink font-medium underline">
                {useCase.title}
              </Link>
              <VerdictChip value={useCase.state} />
              {useCase.eu_tier && (
                <TierBadge value={toTierMember(useCase.eu_tier)} variant="compact" />
              )}
              {court && (
                <WhoseCourtIndicator
                  partyLabel={court.partyLabel}
                  isYourCourt={isYourCourt(court, roleKeys)}
                />
              )}
            </li>
          );
        })}
      </ul>
    </li>
  );
}
