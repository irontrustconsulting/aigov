"use client";

import { useState } from "react";
import { useCreateControlLink, useDeleteControlLink, useControls } from "@/lib/assess";
import type { AssessmentItemRead } from "@irontrust/api-client";

interface Props {
  item: AssessmentItemRead;
  assessmentId: string;
  /** True when the caller has gov:write and the assessment is not locked. */
  canWrite: boolean;
}

/**
 * Control links for an assessment item (WI-5, INV-20).
 * Free on any item including AI_SUGGESTED (asymmetry vs evidence-links).
 * Multi-homed controls show all framework references (CTL-2).
 */
export function ControlLinks({ item, assessmentId, canWrite }: Props) {
  const [showPicker, setShowPicker] = useState(false);
  const [selectedControlId, setSelectedControlId] = useState("");

  const controlsQuery = useControls();
  const createLink = useCreateControlLink(assessmentId);
  const deleteLink = useDeleteControlLink(assessmentId);

  function handleCreate() {
    if (!selectedControlId) return;
    createLink.mutate(
      { itemId: item.id, body: { control_id: selectedControlId } },
      { onSuccess: () => { setShowPicker(false); setSelectedControlId(""); } }
    );
  }

  const linkedControlIds = new Set(item.control_links.map((l) => l.control_id));

  return (
    <div aria-label="control-links">
      {item.control_links.length > 0 && (
        <ul aria-label="linked-controls" className="space-y-1 mb-2">
          {item.control_links.map((link) => {
            const control = controlsQuery.data?.find((c) => c.id === link.control_id);
            return (
              <li key={link.id} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-ink-muted">
                  {control ? `${control.code} — ${control.title}` : link.control_id}
                  {/* Multi-homed: show all framework homes (CTL-2) */}
                  {control && control.frameworks.length > 0 && (
                    <span aria-label="frameworks">
                      {" ("}
                      {control.frameworks.map((f) => `${f.framework} ${f.clause_ref}`).join(", ")}
                      {")"}
                    </span>
                  )}
                </span>
                {canWrite && (
                  <button
                    onClick={() => deleteLink.mutate({ itemId: item.id, linkId: link.id })}
                    disabled={deleteLink.isPending}
                    aria-label={`unlink-control-${link.id}`}
                    className="border-hairline rounded border px-2 py-0.5 text-xs disabled:opacity-50"
                  >
                    Unlink
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {canWrite && (
        showPicker ? (
          <div aria-label="control-picker" className="flex flex-wrap items-center gap-2">
            <select
              value={selectedControlId}
              onChange={(e) => setSelectedControlId(e.target.value)}
              disabled={controlsQuery.isLoading}
              className="border-hairline rounded border px-2 py-1 text-sm"
            >
              <option value="">Select a control…</option>
              {(controlsQuery.data ?? [])
                .filter((c) => !linkedControlIds.has(c.id))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.title}
                  </option>
                ))}
            </select>
            <button onClick={handleCreate} disabled={!selectedControlId || createLink.isPending} className="border-hairline rounded border px-3 py-1.5 text-sm disabled:opacity-50">
              {createLink.isPending ? "Linking…" : "Link"}
            </button>
            <button onClick={() => { setShowPicker(false); setSelectedControlId(""); }} className="border-hairline rounded border px-3 py-1.5 text-sm">
              Cancel
            </button>
          </div>
        ) : (
          <button onClick={() => setShowPicker(true)} className="border-hairline rounded border px-3 py-1.5 text-sm">Link control</button>
        )
      )}
    </div>
  );
}
