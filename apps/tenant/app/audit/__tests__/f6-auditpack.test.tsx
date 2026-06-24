/**
 * @jest-environment jsdom
 *
 * F6 visual done-checks (UI-V1-TENANT-SKIN):
 * - downgraded_unsubstantiated renders data-verdict="downgraded" tag (INV-51/OPEN-V6)
 * - downgraded tag absent for native PARTIAL verdict
 * - AuditPackView root has font-serif class (INV-65)
 * - AtoDocumentView root has font-serif class (INV-65)
 * - Drift caveat renders before ATO detail dl (DOM order / INV-44)
 */
import { render, screen } from "@testing-library/react";
import { CoverageMatrix, AuditPackView, AtoDocumentView } from "@irontrust/ui";
import type {
  CoverageMatrixRead,
  UseCaseExportRead,
  AtoDocumentRead,
} from "@irontrust/api-client";

// ---------------------------------------------------------------------------
// Minimal fixtures
// ---------------------------------------------------------------------------

function makeMatrix(verdict: string): CoverageMatrixRead {
  return {
    scope: "use_case",
    scope_id: "uc-1",
    framework_filter: null,
    include_unapproved: false,
    not_an_obligation_set: false,
    generated_at: "2024-03-01T10:00:00Z",
    unaddressed_controls: [],
    frameworks: [],
    controls: [
      {
        control_id: "ctrl-1",
        code: "4.2.1",
        title: "Data governance",
        verdict,
        breakdown: {
          satisfied: verdict === "SATISFIED" ? 1 : 0,
          partial: verdict === "PARTIAL" || verdict === "downgraded_unsubstantiated" ? 1 : 0,
          open: verdict === "OPEN" ? 1 : 0,
          downgraded_unsubstantiated: verdict === "downgraded_unsubstantiated" ? 1 : 0,
          contributing_refs: [],
        },
        framework_mappings: [],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// CoverageMatrix — downgraded_unsubstantiated rendering
// ---------------------------------------------------------------------------

describe("F6 CoverageMatrix — downgraded_unsubstantiated verdict", () => {
  test("renders data-verdict='downgraded' tag for downgraded_unsubstantiated", () => {
    const { container } = render(
      <CoverageMatrix matrix={makeMatrix("downgraded_unsubstantiated")} label="Coverage" />
    );
    const tag = container.querySelector("[data-verdict='downgraded']");
    expect(tag).not.toBeNull();
    expect(tag?.textContent).toBe("downgraded");
  });

  test("downgraded tag absent for native PARTIAL", () => {
    const { container } = render(
      <CoverageMatrix matrix={makeMatrix("PARTIAL")} label="Coverage" />
    );
    expect(container.querySelector("[data-verdict='downgraded']")).toBeNull();
  });

  test("downgraded_unsubstantiated renders PARTIAL chip (data-tone=attention)", () => {
    const { container } = render(
      <CoverageMatrix matrix={makeMatrix("downgraded_unsubstantiated")} label="Coverage" />
    );
    const chips = container.querySelectorAll("[data-tone='attention']");
    expect(chips.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// AuditPackView — font-serif root + no URL in DOM
// ---------------------------------------------------------------------------

const MINIMAL_UC_PACK = {
  use_case_id: "uc-1",
  system: { system_id: "sys-1", name: "Risk Tool", use_case_count: 1 },
  content_hash: "abc123",
  generated_at: "2024-03-01T10:00:00Z",
  classification_history: [],
  assessment: {
    aiia_id: null,
    status: null,
    version: null,
    tier_snapshot: null,
    native_items: [],
    feeders: [],
  },
  evidence_manifest: [],
  coverage: makeMatrix("SATISFIED"),
  lifecycle_trail: [],
  audit_trail: [],
  atos: [],
} as unknown as UseCaseExportRead;

describe("F6 AuditPackView — serif face (INV-65)", () => {
  test("root article has font-serif class", () => {
    const { container } = render(
      <AuditPackView pack={MINIMAL_UC_PACK} onDownloadEvidence={jest.fn()} />
    );
    const article = container.querySelector("article[aria-label='audit-pack-view']");
    expect(article?.classList.contains("font-serif")).toBe(true);
  });

  test("no presigned URL in DOM (INV-40)", () => {
    render(<AuditPackView pack={MINIMAL_UC_PACK} onDownloadEvidence={jest.fn()} />);
    expect(document.body.innerHTML).not.toMatch(/https?:\/\//);
  });
});

// ---------------------------------------------------------------------------
// AtoDocumentView — serif face + drift caveat order (INV-44, INV-65)
// ---------------------------------------------------------------------------

const MINIMAL_ATO_DOC: AtoDocumentRead = {
  ato: {
    id: "ato-1",
    use_case_id: "uc-1",
    tier: "HIGH",
    submission_round: 1,
    residual_risk_statement: "Residual risk is acceptable.",
    authorised_by_name: "Alice Smith",
    authorised_by_email: "alice@example.com",
    authorised_at: "2024-03-01T10:00:00Z",
    live_state: "AUTHORISED",
  },
  current_assessment_summary: {
    aiia_id: "aiia-1",
    status: "authorised",
    type: "AIIA",
    tier_snapshot: "HIGH",
    version: 2,
  },
  current_classification_summary: {
    id: "cls-1",
    tier: "HIGH",
    status: "confirmed",
    version: 2,
    rationale: "Annex III applies.",
  },
} as unknown as AtoDocumentRead;

describe("F6 AtoDocumentView — serif face + drift caveat order (INV-44, INV-65)", () => {
  test("root article has font-serif class", () => {
    const { container } = render(<AtoDocumentView doc={MINIMAL_ATO_DOC} />);
    const article = container.querySelector("article[aria-label='ato-document']");
    expect(article?.classList.contains("font-serif")).toBe(true);
  });

  test("drift caveat renders before ATO detail section (DOM order)", () => {
    const { container } = render(<AtoDocumentView doc={MINIMAL_ATO_DOC} />);
    const caveat = container.querySelector("[aria-label='ato-drift-caveat']")!;
    const details = container.querySelector("[aria-label='ato-details']")!;
    // caveat precedes details: details follows caveat in document order
    expect(
      caveat.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING
    ).not.toBe(0);
  });

  test("drift caveat uses V0 edge-bar (no warning-* Tailwind classes)", () => {
    const { container } = render(<AtoDocumentView doc={MINIMAL_ATO_DOC} />);
    const caveat = container.querySelector("[aria-label='ato-drift-caveat']")!;
    expect(caveat.className).not.toContain("warning");
    expect(caveat.className).toContain("bg-surface");
  });
});
