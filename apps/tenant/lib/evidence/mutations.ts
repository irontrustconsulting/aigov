"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { EvidenceRead } from "@irontrust/api-client";
import { api } from "@/lib/api";
import { evidenceKeys } from "./query-keys";

/**
 * Upload evidence via the dedicated BFF handler (FE-12, DF5-2, WI-C).
 * Posts multipart/form-data to /api/evidence-upload — NOT the generic proxy.
 * Binary file bytes are forwarded as-is; the proxy's request.text() would
 * corrupt them (V-8).
 * On success: invalidates the evidence list.
 */
export function useUploadEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, title }: { file: File; title?: string }) => {
      const body = new FormData();
      body.append("file", file);
      if (title) body.append("title", title);
      const response = await fetch("/api/evidence-upload", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        const text = await response.text();
        let message: string;
        try {
          message = (JSON.parse(text) as { error?: string }).error ?? text;
        } catch {
          message = text;
        }
        throw new Error(message);
      }
      return response.json() as Promise<EvidenceRead>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: evidenceKeys.list() });
    },
  });
}

/** DELETE /v1/evidence/{id} (gov:write). Pristine guard (INV-19): server rejects when linked. */
export function useDeleteEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ evidenceId }: { evidenceId: string }) =>
      api.delete(`/v1/evidence/${evidenceId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: evidenceKeys.list() });
    },
  });
}
