"use client";

import { useQuery } from "@tanstack/react-query";
import { useLiveState } from "@irontrust/api-client";
import type {
  AffectedPartyOut,
  ClassificationContextRead,
  DataCategoryOut,
  EUAIActSubcategoryRead,
  MeRead,
  PrefillResponse,
  ProductCategoryRead,
  ProductDetailOut,
  ProductRead,
  UseCaseLifecycleRead,
  VendorRead,
  VocabItemOut,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { intakeKeys, lifecycleKey } from "./query-keys";

// ---------------------------------------------------------------------------
// Drill-down (WI-4)
// ---------------------------------------------------------------------------

export function useProductCategories(parentId?: string) {
  return useQuery({
    queryKey: intakeKeys.productCategories(parentId),
    queryFn: () =>
      api.get<ProductCategoryRead[]>(
        parentId
          ? `/v1/reference/product-categories?parent_id=${parentId}`
          : "/v1/reference/product-categories"
      ),
  });
}

export function useVendorsInCategory(categoryId: string) {
  return useQuery({
    queryKey: intakeKeys.vendorsInCategory(categoryId),
    queryFn: () => api.get<VendorRead[]>(`/v1/reference/product-categories/${categoryId}/vendors`),
    enabled: Boolean(categoryId),
  });
}

export function useProductsInCategory(categoryId: string, vendorId?: string) {
  return useQuery({
    queryKey: intakeKeys.productsInCategory(categoryId, vendorId),
    queryFn: () =>
      api.get<ProductRead[]>(
        vendorId
          ? `/v1/reference/product-categories/${categoryId}/products?vendor_id=${vendorId}`
          : `/v1/reference/product-categories/${categoryId}/products`
      ),
    enabled: Boolean(categoryId),
  });
}

export function useProductDetail(productId: string | undefined) {
  return useQuery({
    queryKey: intakeKeys.productDetail(productId ?? ""),
    queryFn: () => api.get<ProductDetailOut>(`/v1/reference/products/${productId}`),
    enabled: Boolean(productId),
  });
}

export function useEUSubcategories() {
  return useQuery({
    queryKey: intakeKeys.euSubcategories(),
    queryFn: () => api.get<EUAIActSubcategoryRead[]>("/v1/reference/eu-ai-act/subcategories"),
  });
}

// ---------------------------------------------------------------------------
// Intake-vocab lists (WI-0 / WI-5)
// ---------------------------------------------------------------------------

export function useOperatorRoles() {
  return useQuery({
    queryKey: intakeKeys.operatorRoles(),
    queryFn: () => api.get<VocabItemOut[]>("/v1/reference/operator-roles"),
  });
}

export function useHostingModels() {
  return useQuery({
    queryKey: intakeKeys.hostingModels(),
    queryFn: () => api.get<VocabItemOut[]>("/v1/reference/hosting-models"),
  });
}

export function useUsageContexts() {
  return useQuery({
    queryKey: intakeKeys.usageContexts(),
    queryFn: () => api.get<VocabItemOut[]>("/v1/reference/usage-contexts"),
  });
}

export function useHumanOversightTypes() {
  return useQuery({
    queryKey: intakeKeys.humanOversightTypes(),
    queryFn: () => api.get<VocabItemOut[]>("/v1/reference/human-oversight-types"),
  });
}

export function useDataCategories() {
  return useQuery({
    queryKey: intakeKeys.dataCategories(),
    queryFn: () => api.get<DataCategoryOut[]>("/v1/reference/data-categories"),
  });
}

export function useAffectedParties() {
  return useQuery({
    queryKey: intakeKeys.affectedParties(),
    queryFn: () => api.get<AffectedPartyOut[]>("/v1/reference/affected-parties"),
  });
}

// ---------------------------------------------------------------------------
// Prefill (WI-6)
// ---------------------------------------------------------------------------

export function usePrefill(catalogueProductId: string | null | undefined) {
  return useQuery({
    queryKey: intakeKeys.prefill(catalogueProductId ?? ""),
    queryFn: () =>
      api.get<PrefillResponse>(`/v1/catalogue/products/${catalogueProductId}/prefill`),
    enabled: Boolean(catalogueProductId),
  });
}

// ---------------------------------------------------------------------------
// Context gate (WI-8)
// ---------------------------------------------------------------------------

export function useClassificationContext(useCaseId: string | undefined) {
  return useQuery({
    queryKey: intakeKeys.classificationContext(useCaseId ?? ""),
    queryFn: () =>
      api.get<ClassificationContextRead>(`/v1/use-cases/${useCaseId}/classification/context`),
    enabled: Boolean(useCaseId),
  });
}

// ---------------------------------------------------------------------------
// Whose-court (WI-9) — live state, FE-7/INV-25: useLiveState, never useQuery.
// useLiveState has no `enabled` escape hatch by design (no options param at
// all — see use-live-state.ts), so callers only mount the WI-9 surface once
// a use case id exists, rather than calling this hook conditionally.
// ---------------------------------------------------------------------------

export function useUseCaseLifecycle(useCaseId: string) {
  return useLiveState(lifecycleKey(useCaseId), () =>
    api.get<UseCaseLifecycleRead>(`/v1/use-cases/${useCaseId}/lifecycle`)
  );
}

// ---------------------------------------------------------------------------
// Role context (WI-7 SoD gating / WI-10)
// ---------------------------------------------------------------------------

export function useMe() {
  return useQuery({
    queryKey: intakeKeys.me(),
    queryFn: () => api.get<MeRead>("/v1/me"),
  });
}
