import type { ReactNode } from "react";
import type { CatalogueFactOut } from "@irontrust/api-client";

/** Formats an ISO datetime string as "D MMM YYYY" (British, e.g. "1 Apr 2025"). */
export function formatFactDate(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleDateString("en-GB", { day: "numeric", timeZone: "UTC" });
  const month = d.toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" });
  const year = d.toLocaleDateString("en-GB", { year: "numeric", timeZone: "UTC" });
  return `${day} ${month} ${year}`;
}

/** Composes the basis line for a catalogue fact card (R5). */
export function composeBasis(fact: CatalogueFactOut): ReactNode {
  if (!fact.source_label) return "From the product catalogue";

  const dateStr = fact.last_checked_at
    ? ` · checked ${formatFactDate(fact.last_checked_at)}`
    : "";

  const sourceNode = fact.source_url ? (
    <a
      href={fact.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="underline"
    >
      {fact.source_label}
    </a>
  ) : (
    fact.source_label
  );

  return (
    <>
      {sourceNode}
      {dateStr}
    </>
  );
}
