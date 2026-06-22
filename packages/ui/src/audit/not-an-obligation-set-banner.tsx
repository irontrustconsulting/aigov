import type { UnaddressedControlRead } from "@irontrust/api-client";

interface Props {
  unaddressedControls: UnaddressedControlRead[];
}

/**
 * INV-52 / DF6-4: coverage gaps rendered as gaps, never failures.
 * No compliance-% headline while applicability (OPEN-3) is pending.
 */
export function NotAnObligationSetBanner({ unaddressedControls }: Props) {
  return (
    <div
      role="note"
      aria-label="not-an-obligation-set-banner"
      className="bg-warning-subtle border-warning text-warning-fg rounded border px-4 py-3 text-sm"
    >
      <p className="font-medium">
        Coverage gaps shown — not an obligation set (applicability layer pending).
      </p>
      {unaddressedControls.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer">
            {unaddressedControls.length} control
            {unaddressedControls.length === 1 ? "" : "s"} not yet addressed
          </summary>
          <ul className="mt-1 list-disc pl-5">
            {unaddressedControls.map((c) => (
              <li key={c.control_id}>
                <span className="font-mono text-xs">{c.code}</span> — {c.title}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
