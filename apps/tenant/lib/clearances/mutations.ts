"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ProductApprovalCreate,
  ProductApprovalRead,
  VendorApprovalCreate,
  VendorApprovalRead,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { portfolioKey } from "@/lib/portfolio/query-keys";
import { clearanceQueueKey } from "./query-keys";

/** PUT /v1/vendors/{id}/approval — the authoriser-only clearance act
 * (gov:authoriser, server-gated). Fans out on the backend; on success
 * invalidate the clearance queue and the portfolio rollup, both of which
 * can now show a different resting gate for affected use cases. */
export function useSetVendorApproval(vendorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorApprovalCreate) =>
      api.put<VendorApprovalRead, VendorApprovalCreate>(
        `/v1/vendors/${vendorId}/approval`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clearanceQueueKey() });
      queryClient.invalidateQueries({ queryKey: portfolioKey() });
    },
  });
}

/** PUT /v1/products/{id}/approval — same shape as useSetVendorApproval. */
export function useSetProductApproval(productId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ProductApprovalCreate) =>
      api.put<ProductApprovalRead, ProductApprovalCreate>(
        `/v1/products/${productId}/approval`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clearanceQueueKey() });
      queryClient.invalidateQueries({ queryKey: portfolioKey() });
    },
  });
}
