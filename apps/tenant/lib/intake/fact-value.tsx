import type { ReactNode } from "react";

type FactShape = Record<string, unknown>;

const ARRAY_PRIORITY_KEYS = ["list", "regions", "models"] as const;
const STRING_PRIORITY_KEYS = ["standard", "entity", "framework"] as const;

function BoolChip({ value }: { value: boolean }): ReactNode {
  return (
    <span
      className="inline-flex items-center rounded border border-hairline bg-surface-sunken px-2 py-0.5 text-sm text-ink"
      data-fact-value=""
      data-bool={String(value)}
    >
      {value ? "Yes" : "No"}
    </span>
  );
}

function Pill({ label }: { label: string }): ReactNode {
  return (
    <span
      className="inline-flex items-center rounded border border-hairline bg-surface-sunken px-2 py-0.5 text-sm text-ink"
      data-fact-value=""
    >
      {label}
    </span>
  );
}

function NoteLine({ text }: { text: string }): ReactNode {
  return <p className="text-xs text-ink-muted">{text}</p>;
}

/** §3 value projection — shape-typed; never JSON.stringify, never String(array). INV-84. */
export function FactValue({ value }: { value: FactShape }): ReactNode {
  // Branch 1: boolean answer → Yes/No chip; note → muted line; url → Source link.
  if (typeof value.answer === "boolean") {
    const note = typeof value.note === "string" ? value.note : undefined;
    const url = typeof value.url === "string" ? value.url : undefined;
    return (
      <div className="space-y-1">
        <BoolChip value={value.answer} />
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-xs text-brand underline"
          >
            Source
          </a>
        )}
        {note && <NoteLine text={note} />}
      </div>
    );
  }

  // Branch 2: array-valued key (priority list|regions|models, else any array) → pill cluster.
  const arrayKey =
    (ARRAY_PRIORITY_KEYS as readonly string[]).find((k) => Array.isArray(value[k])) ??
    Object.keys(value).find((k) => k !== "note" && Array.isArray(value[k]));
  if (arrayKey !== undefined) {
    const items = value[arrayKey] as unknown[];
    const note = typeof value.note === "string" ? value.note : undefined;
    return (
      <div className="space-y-1">
        <div className="flex flex-wrap gap-1">
          {items.map((item, i) => (
            <Pill key={i} label={String(item)} />
          ))}
        </div>
        {note && <NoteLine text={note} />}
      </div>
    );
  }

  // Branch 3: string-valued key (priority standard|entity|framework, else any string non-note/url) → plain text.
  const stringKey =
    (STRING_PRIORITY_KEYS as readonly string[]).find((k) => typeof value[k] === "string") ??
    Object.keys(value).find(
      (k) => k !== "note" && k !== "url" && typeof value[k] === "string"
    );
  if (stringKey !== undefined) {
    const note = typeof value.note === "string" ? value.note : undefined;
    return (
      <div className="space-y-1">
        <span className="text-sm text-ink">{value[stringKey] as string}</span>
        {note && <NoteLine text={note} />}
      </div>
    );
  }

  // Branch 4: note only → note text is the value.
  if (Object.keys(value).length === 1 && typeof value.note === "string") {
    return <span className="text-sm text-ink">{value.note}</span>;
  }

  // Branch 5: residual → definition list; note excluded from dl, appended below. No JSON.stringify.
  const note = typeof value.note === "string" ? value.note : undefined;
  const entries = Object.entries(value).filter(([k]) => k !== "note");
  return (
    <div className="space-y-1">
      <dl className="space-y-0.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-1 text-sm text-ink">
            <dt className="font-medium">{k}:</dt>
            <dd>
              {typeof v === "string" || typeof v === "number" || typeof v === "boolean"
                ? String(v)
                : "(complex value)"}
            </dd>
          </div>
        ))}
      </dl>
      {note && <NoteLine text={note} />}
    </div>
  );
}
