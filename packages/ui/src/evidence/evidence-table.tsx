import { SodAction } from "../sod-wrapper/sod-action";
import { Table, TableHeaderRow, TableRow, TableCell } from "../primitives/table";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export interface EvidenceRow {
  id: string;
  title: string;
  content_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  created_at: string;
  link_count: number;
}

interface Props {
  items: EvidenceRow[];
  onDownload: (id: string) => void;
  /** Undefined = caller is read-only (reviewer/authoriser/auditor). FE-8. */
  onDelete?: (id: string) => void;
}

/**
 * Evidence repository table. Delete is present only when `onDelete` is provided
 * (FE-8); it is disabled-with-reason when link_count > 0 (INV-19, DF5-6).
 * No uploader column — uploaded_by_user_id is a bare UUID in MVP (DF5-11).
 */
export function EvidenceTable({ items, onDownload, onDelete }: Props) {
  if (items.length === 0) {
    return <p className="text-text-muted text-sm">No evidence uploaded yet.</p>;
  }

  return (
    <Table>
      <TableHeaderRow>
        <th className="px-3 py-2 text-left font-medium">Title</th>
        <th className="px-3 py-2 text-left font-medium">Type</th>
        <th className="px-3 py-2 text-left font-medium">Size</th>
        <th className="px-3 py-2 text-left font-medium">SHA-256</th>
        <th className="px-3 py-2 text-left font-medium">Uploaded</th>
        <th className="px-3 py-2 text-left font-medium">Links</th>
        <th className="px-3 py-2 text-left font-medium">Actions</th>
      </TableHeaderRow>
      {items.map((item) => (
        <TableRow key={item.id}>
          <TableCell>{item.title}</TableCell>
          <TableCell>{item.content_type ?? "—"}</TableCell>
          <TableCell>{formatBytes(item.size_bytes)}</TableCell>
          <TableCell>
            <span className="font-mono text-xs" title={item.sha256 ?? undefined}>
              {item.sha256 ? `${item.sha256.slice(0, 12)}…` : "—"}
            </span>
          </TableCell>
          <TableCell>{new Date(item.created_at).toLocaleDateString()}</TableCell>
          <TableCell>{item.link_count}</TableCell>
          <TableCell>
            <button type="button" onClick={() => onDownload(item.id)} className="text-sm underline">
              Download
            </button>
            {onDelete && (
              <SodAction
                barred={false}
                blockedReason={
                  item.link_count > 0
                    ? `Cannot delete — linked to ${item.link_count} item${item.link_count === 1 ? "" : "s"}`
                    : null
                }
              >
                <button
                  type="button"
                  onClick={() => onDelete(item.id)}
                  className="ml-2 text-sm underline"
                >
                  Delete
                </button>
              </SodAction>
            )}
          </TableCell>
        </TableRow>
      ))}
    </Table>
  );
}
