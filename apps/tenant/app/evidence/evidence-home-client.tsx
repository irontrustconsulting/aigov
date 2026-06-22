"use client";

import { useEffect, useState } from "react";
import {
  EvidenceTable,
  EvidenceUploadControl,
  type EvidenceRow,
} from "@irontrust/ui";
import { useMe } from "@/lib/intake";
import {
  useEvidenceList,
  useEvidenceDetail,
  useUploadEvidence,
  useDeleteEvidence,
} from "@/lib/evidence";

/**
 * Evidence repository home (UI-F5-EVIDENCE WI-D, DF5-7).
 * Role branch via GET /v1/me:
 *   admin (zero gov roles)  → empty-state, no evidence request issued
 *   reviewer/authoriser/auditor → list + download (upload/delete absent, FE-8)
 *   system_owner/contributor  → list + upload + download + delete
 */
export function EvidenceHomeClient() {
  const me = useMe();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const govRoleKeys = me.data.governance_roles.map((r) => r.key);
  const hasGovRole = govRoleKeys.length > 0;

  if (!hasGovRole) {
    return (
      <main aria-label="evidence-repository">
        <h1>Evidence repository</h1>
        <p>Evidence is not available for your current role.</p>
      </main>
    );
  }

  const canWrite =
    govRoleKeys.includes("system_owner") || govRoleKeys.includes("contributor");

  return <EvidenceRepository canWrite={canWrite} />;
}

function EvidenceRepository({ canWrite }: { canWrite: boolean }) {
  const listQuery = useEvidenceList();
  const uploadMutation = useUploadEvidence();
  const deleteMutation = useDeleteEvidence();

  // Download on-intent: fetch the detail only when an id is pending (DF5-3).
  const [pendingDownloadId, setPendingDownloadId] = useState<string>("");
  const detailQuery = useEvidenceDetail(pendingDownloadId, Boolean(pendingDownloadId));

  useEffect(() => {
    if (pendingDownloadId && detailQuery.data) {
      window.location.href = detailQuery.data.download_url;
      setPendingDownloadId("");
    }
  }, [pendingDownloadId, detailQuery.data]);

  const [uploadError, setUploadError] = useState<string | undefined>();

  function handleUpload(file: File, title?: string) {
    setUploadError(undefined);
    uploadMutation.mutate(
      { file, title },
      { onError: (err) => setUploadError(err instanceof Error ? err.message : "Upload failed") }
    );
  }

  if (listQuery.isLoading) return <p>Loading evidence…</p>;
  if (listQuery.isError) return <p role="alert">Could not load evidence.</p>;

  const items: EvidenceRow[] = (listQuery.data?.items ?? []).map((ev) => ({
    id: ev.id,
    title: ev.title,
    content_type: ev.content_type,
    size_bytes: ev.size_bytes,
    sha256: ev.sha256,
    created_at: ev.created_at,
    link_count: ev.link_count,
  }));

  return (
    <main aria-label="evidence-repository">
      <h1>Evidence repository</h1>

      {canWrite && (
        <section aria-label="upload-evidence">
          <h2>Upload evidence</h2>
          <EvidenceUploadControl
            onUpload={handleUpload}
            isPending={uploadMutation.isPending}
            error={uploadError}
          />
        </section>
      )}

      <section aria-label="evidence-list">
        <h2>All evidence</h2>
        <EvidenceTable
          items={items}
          onDownload={(id) => setPendingDownloadId(id)}
          onDelete={
            canWrite
              ? (id) => deleteMutation.mutate({ evidenceId: id })
              : undefined
          }
        />
      </section>
    </main>
  );
}
