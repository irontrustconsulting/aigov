import type { EvidenceManifestEntryRead } from "@irontrust/api-client";
import { Table, TableBody, TableHeaderRow, TableRow, TableCell } from "../primitives/table";

interface Props {
  entries: EvidenceManifestEntryRead[];
  /** Caller constructs GET /v1/evidence/{id} on-intent (INV-40, INV-22, DF5-3).
   * Never a URL in props — no bytes, no embedded presigned URL. */
  onDownload: (id: string) => void;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Evidence manifest table — no URLs, no bytes (INV-40).
 * Download constructs GET /v1/evidence/{id} via callback (hardened route, INV-22).
 */
export function EvidenceManifestTable({ entries, onDownload }: Props) {
  if (entries.length === 0) {
    return <p className="text-ink-muted text-sm">No evidence in this manifest.</p>;
  }

  return (
    <Table>
      <TableHeaderRow>
        <th className="px-3 py-2 text-left font-medium">Title</th>
        <th className="px-3 py-2 text-left font-medium">Type</th>
        <th className="px-3 py-2 text-left font-medium">Size</th>
        <th className="px-3 py-2 text-left font-medium">SHA-256</th>
        <th className="px-3 py-2 text-left font-medium">References</th>
        <th className="px-3 py-2 text-left font-medium">Download</th>
      </TableHeaderRow>
      <TableBody>
      {entries.map((entry) => (
        <TableRow key={entry.id}>
          <TableCell>{entry.title}</TableCell>
          <TableCell>{entry.content_type ?? "—"}</TableCell>
          <TableCell>{formatBytes(entry.size_bytes)}</TableCell>
          <TableCell>
            <span className="font-mono text-xs" title={entry.sha256 ?? undefined}>
              {entry.sha256 ? `${entry.sha256.slice(0, 12)}…` : "—"}
            </span>
          </TableCell>
          <TableCell>{entry.back_refs.length}</TableCell>
          <TableCell>
            <button
              type="button"
              className="text-brand text-sm underline"
              onClick={() => onDownload(entry.id)}
            >
              Download
            </button>
          </TableCell>
        </TableRow>
      ))}
      </TableBody>
    </Table>
  );
}
