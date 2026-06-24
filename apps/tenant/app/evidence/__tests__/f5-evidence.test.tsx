/**
 * @jest-environment jsdom
 *
 * F5 visual done-checks (UI-V1-TENANT-SKIN):
 * - EvidenceTable renders link_count ("Links" column)
 * - EvidenceManifestTable renders back_refs count ("References" — not link_count)
 * - No evidence URL in DOM (INV-40, DF5-3)
 * - EvidenceManifest AI_SUGGESTED gate: link control disabled-with-reason
 */
import { render, screen } from "@testing-library/react";
import { EvidenceTable } from "@irontrust/ui";
import { EvidenceManifestTable } from "@irontrust/ui";
import type { EvidenceManifestEntryRead } from "@irontrust/api-client";

// ---------------------------------------------------------------------------
// EvidenceTable — repository view
// ---------------------------------------------------------------------------

const EVIDENCE_ROWS = [
  {
    id: "ev-1",
    title: "Risk Assessment Report",
    content_type: "application/pdf",
    size_bytes: 204800,
    sha256: "abc123def456789012345678901234567890123456789012345678901234",
    created_at: "2024-03-01T10:00:00Z",
    link_count: 3,
  },
  {
    id: "ev-2",
    title: "Privacy Impact Assessment",
    content_type: "application/pdf",
    size_bytes: 102400,
    sha256: "xyz999aaa111222333444555666777888999000111222333444555666777",
    created_at: "2024-03-02T10:00:00Z",
    link_count: 0,
  },
];

describe("F5 EvidenceTable — repository view", () => {
  test("renders Links column showing link_count value", () => {
    render(
      <EvidenceTable
        items={EVIDENCE_ROWS}
        onDownload={jest.fn()}
        onDelete={jest.fn()}
      />
    );
    expect(screen.getByRole("columnheader", { name: "Links" })).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  test("no evidence URL in DOM (INV-40)", () => {
    render(
      <EvidenceTable
        items={EVIDENCE_ROWS}
        onDownload={jest.fn()}
      />
    );
    expect(document.body.innerHTML).not.toMatch(/https?:\/\//);
  });

  test("delete absent for read-only caller (onDelete undefined)", () => {
    render(
      <EvidenceTable items={EVIDENCE_ROWS} onDownload={jest.fn()} />
    );
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  test("delete disabled-with-reason when link_count > 0 (INV-19)", () => {
    render(
      <EvidenceTable items={EVIDENCE_ROWS} onDownload={jest.fn()} onDelete={jest.fn()} />
    );
    // EVIDENCE_ROWS[0] has link_count=3; SodAction renders the Delete button disabled
    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    const disabledDelete = deleteButtons.find((b) => (b as HTMLButtonElement).disabled);
    expect(disabledDelete).not.toBeUndefined();
    // Blocked reason is rendered as a note
    const reasonNotes = screen.getAllByRole("note");
    expect(reasonNotes.length).toBeGreaterThanOrEqual(1);
    expect(reasonNotes.some((n) => n.textContent?.includes("Cannot delete"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// EvidenceManifestTable — audit-pack view (distinct shape)
// ---------------------------------------------------------------------------

const MANIFEST_ENTRIES: EvidenceManifestEntryRead[] = [
  {
    id: "ev-1",
    evidence_id: "ev-1",
    title: "Risk Assessment Report",
    content_type: "application/pdf",
    size_bytes: 204800,
    sha256: "abc123def456789012345678901234567890123456789012345678901234",
    back_refs: [{ item_id: "item-1", prompt_excerpt: "Does this system..." }],
  } as unknown as EvidenceManifestEntryRead,
];

describe("F5 EvidenceManifestTable — audit-pack view", () => {
  test("renders References column (not link_count column)", () => {
    render(<EvidenceManifestTable entries={MANIFEST_ENTRIES} onDownload={jest.fn()} />);
    expect(screen.getByRole("columnheader", { name: "References" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Links" })).not.toBeInTheDocument();
  });

  test("no evidence URL in DOM (INV-40)", () => {
    render(<EvidenceManifestTable entries={MANIFEST_ENTRIES} onDownload={jest.fn()} />);
    expect(document.body.innerHTML).not.toMatch(/https?:\/\//);
  });

  test("back_refs count is displayed (1 for MANIFEST_ENTRIES[0])", () => {
    const { container } = render(
      <EvidenceManifestTable entries={MANIFEST_ENTRIES} onDownload={jest.fn()} />
    );
    const cells = container.querySelectorAll("td");
    const refCell = Array.from(cells).find((c) => c.textContent === "1");
    expect(refCell).not.toBeUndefined();
  });
});
