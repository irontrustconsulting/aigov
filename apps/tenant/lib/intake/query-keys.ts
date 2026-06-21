/** Query keys for the intake wizard (WI-3). Lifecycle is the one live-state
 * read here (FE-7) — its key must satisfy `LiveStateQueryKey`
 * (`@irontrust/api-client`), enforced by the `no-raw-live-state-query`
 * eslint rule. */
export const intakeKeys = {
  productCategories: (parentId?: string) => ["product-categories", parentId ?? null] as const,
  vendorsInCategory: (categoryId: string) => ["vendors-in-category", categoryId] as const,
  productsInCategory: (categoryId: string, vendorId?: string) =>
    ["products-in-category", categoryId, vendorId ?? null] as const,
  productDetail: (productId: string) => ["product-detail", productId] as const,
  euSubcategories: () => ["eu-ai-act-subcategories"] as const,
  operatorRoles: () => ["operator-roles"] as const,
  hostingModels: () => ["hosting-models"] as const,
  usageContexts: () => ["usage-contexts"] as const,
  humanOversightTypes: () => ["human-oversight-types"] as const,
  dataCategories: () => ["data-categories"] as const,
  affectedParties: () => ["affected-parties"] as const,
  prefill: (systemId: string) => ["system-prefill", systemId] as const,
  classificationContext: (useCaseId: string) => ["classification-context", useCaseId] as const,
  me: () => ["me"] as const,
} as const;

/** FE-7 / INV-25: lifecycle is a live-state verdict — its key must go
 * through useLiveState, never a raw useQuery. */
export function lifecycleKey(useCaseId: string) {
  return ["lifecycle-state", useCaseId] as const;
}
