export interface ManifestLink {
  evidence_id: string;
  title: string;
  sha256: string | null;
  content_type: string | null;
}

interface Props {
  link: ManifestLink;
  /** Provided for write roles; absent (undefined) for read-only roles (FE-8). */
  onUnlink?: (evidenceId: string) => void;
}

/**
 * Per-link chip for the per-item evidence manifest.
 * Renders from ItemEvidenceRead — no download_url, no evidence.access triggered
 * (DF5-3, DF5-8). Unlink targets the evidence_id, not a link-row id (DF5-9).
 */
export function EvidenceManifestChip({ link, onUnlink }: Props) {
  return (
    <span className="border-border inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs">
      <span className="font-medium">{link.title}</span>
      {link.sha256 && (
        <span className="text-text-muted font-mono">{link.sha256.slice(0, 8)}…</span>
      )}
      {link.content_type && (
        <span className="text-text-muted">{link.content_type}</span>
      )}
      {onUnlink && (
        <button
          type="button"
          onClick={() => onUnlink(link.evidence_id)}
          aria-label={`Unlink ${link.title}`}
          className="hover:text-text ml-0.5"
        >
          ×
        </button>
      )}
    </span>
  );
}
