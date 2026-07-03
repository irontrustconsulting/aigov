/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { formatFactDate, composeBasis } from "../fact-basis";
import type { CatalogueFactOut } from "@irontrust/api-client";

function makeFact(overrides: Partial<CatalogueFactOut> = {}): CatalogueFactOut {
  return {
    key: "dpa_available",
    value: { answer: true },
    source_url: null,
    source_label: null,
    last_checked_at: null,
    provenance: "catalogue_curated",
    ...overrides,
  };
}

describe("formatFactDate", () => {
  test("ISO datetime → D MMM YYYY with no raw ISO substring", () => {
    expect(formatFactDate("2025-04-01T00:00:00Z")).toBe("1 Apr 2025");
  });

  test("single-digit day has no leading zero", () => {
    expect(formatFactDate("2024-03-07T00:00:00Z")).toBe("7 Mar 2024");
  });
});

describe("composeBasis", () => {
  test("no source_label → plain 'From the product catalogue'", () => {
    render(<>{composeBasis(makeFact())}</>);
    expect(screen.getByText("From the product catalogue")).toBeInTheDocument();
  });

  test("source_label + source_url → anchor with href", () => {
    render(
      <>
        {composeBasis(
          makeFact({
            source_label: "Vendor documentation",
            source_url: "https://vendor.example/docs",
            last_checked_at: "2025-04-01T00:00:00Z",
          })
        )}
      </>
    );
    const link = screen.getByRole("link", { name: "Vendor documentation" });
    expect(link).toHaveAttribute("href", "https://vendor.example/docs");
    expect(screen.getByText(/1 Apr 2025/)).toBeInTheDocument();
    expect(screen.queryByText(/T00:00:00Z/)).not.toBeInTheDocument();
  });

  test("source_label without source_url → plain text (no anchor)", () => {
    render(
      <>
        {composeBasis(
          makeFact({
            source_label: "Vendor documentation",
            source_url: null,
            last_checked_at: "2025-04-01T00:00:00Z",
          })
        )}
      </>
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText(/Vendor documentation/)).toBeInTheDocument();
  });
});
