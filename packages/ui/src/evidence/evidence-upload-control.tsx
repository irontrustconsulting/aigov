import { useRef } from "react";

interface Props {
  onUpload: (file: File, title?: string) => void;
  isPending: boolean;
  /** Server or size error message — renders when present. */
  error?: string;
}

/**
 * File input + optional title field for evidence upload.
 * Caller gates rendering via role branch (FE-8 — upload is gov:write only).
 * The actual POST goes to the dedicated BFF handler, never through the generic
 * proxy (FE-12, DF5-2).
 */
export function EvidenceUploadControl({ onUpload, isPending, error }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);

  function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const title = titleRef.current?.value.trim() || undefined;
    onUpload(file, title);
    if (fileRef.current) fileRef.current.value = "";
    if (titleRef.current) titleRef.current.value = "";
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          disabled={isPending}
          aria-label="Select file to upload"
          className="text-sm"
        />
        <input
          ref={titleRef}
          type="text"
          placeholder="Title (optional)"
          disabled={isPending}
          className="border-border rounded border px-2 py-1 text-sm"
          aria-label="Evidence title"
        />
        <button
          type="button"
          onClick={handleUpload}
          disabled={isPending}
          aria-busy={isPending}
          className="rounded px-3 py-1 text-sm"
        >
          {isPending ? "Uploading…" : "Upload"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
