"use client";

import { useState } from "react";
import { Dialog } from "../primitives/dialog";

export interface EvidencePickerRow {
  id: string;
  title: string;
  sha256: string | null;
  content_type: string | null;
}

interface Props {
  items: EvidencePickerRow[];
  isLoading: boolean;
  onLink: (evidenceId: string) => void;
  isPending: boolean;
}

/**
 * Paginated evidence picker for per-item linking (A-3).
 * Fetched lazily by the caller on open intent — not pre-fetched per row.
 * Client-side filter over the loaded page; no backend ?q= search in MVP.
 * Selecting an item calls onLink(evidenceId) — no If-Match (DF5-4).
 */
export function EvidenceLinkPicker({ items, isLoading, onLink, isPending }: Props) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");

  const visible = items.filter((ev) =>
    ev.title.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={isPending}
        className="text-sm underline"
      >
        Link evidence…
      </button>
      <Dialog open={open} onOpenChange={setOpen} title="Link evidence">
        <div className="mt-2 flex flex-col gap-3">
          <input
            type="search"
            placeholder="Filter by title…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border-hairline rounded border px-2 py-1 text-sm"
            aria-label="Filter evidence"
          />
          {isLoading ? (
            <p className="text-ink-muted text-sm">Loading…</p>
          ) : visible.length === 0 ? (
            <p className="text-ink-muted text-sm">No evidence matches.</p>
          ) : (
            <ul className="max-h-64 overflow-y-auto" role="listbox" aria-label="Evidence items">
              {visible.map((ev) => (
                <li key={ev.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onClick={() => {
                      onLink(ev.id);
                      setOpen(false);
                      setFilter("");
                    }}
                    disabled={isPending}
                    className="hover:bg-surface-sunken w-full px-2 py-1.5 text-left text-sm"
                  >
                    <span className="font-medium">{ev.title}</span>
                    {ev.sha256 && (
                      <span className="text-ink-muted ml-2 font-mono text-xs">
                        {ev.sha256.slice(0, 10)}…
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Dialog>
    </>
  );
}
