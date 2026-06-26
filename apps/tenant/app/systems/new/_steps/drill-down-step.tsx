"use client";

import { useState, useEffect, useRef } from "react";
import {
  Button,
  EmptyState,
  ErrorState,
  ListSelectRow,
  LogoTile,
  PageHeader,
  PageScaffold,
  Skeleton,
} from "@irontrust/ui";
import {
  useProductCategories,
  useProductDetail,
  useProductsInCategory,
  useVendorsInCategory,
} from "@/lib/intake";

export interface DrillDownResult {
  isCustom: boolean;
  catalogueProductId: string | null;
  catalogueProductName: string | null;
}

function InHouseExit({ onExit }: { onExit: () => void }) {
  return (
    <Button type="button" variant="secondary" onClick={onExit}>
      Not in catalogue / in-house
    </Button>
  );
}

/**
 * DrillDownStep (D-56): in-place single-open accordion.
 * Branch rows (category / sub-category / vendor) use FE-23 branch mode.
 * Leaf rows (product) use ListSelectRow + LogoTile.
 * Vendor level only when >1 vendor (auto-skip otherwise).
 * Mixed-node rule per DF-C2-8: branch-sibling collapse only, leaf rows persist.
 * Four INV-70 states per expansion. DrillDownResult shape unchanged.
 */
export function DrillDownStep({ onComplete }: { onComplete: (result: DrillDownResult) => void }) {
  const [expandedCategoryId, setExpandedCategoryId] = useState<string | null>(null);
  const [expandedSubcategoryId, setExpandedSubcategoryId] = useState<string | null>(null);
  const [expandedVendorId, setExpandedVendorId] = useState<string | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  const vendorAutoSkipPrevented = useRef(false);

  const topCategories = useProductCategories();
  const subCategories = useProductCategories(expandedCategoryId ?? undefined);
  // Direct products on the expanded category (mixed-node DF-C2-8)
  const categoryDirectProducts = useProductsInCategory(expandedCategoryId ?? "", undefined);
  const vendors = useVendorsInCategory(expandedSubcategoryId ?? "");
  const subCategoryProducts = useProductsInCategory(
    expandedSubcategoryId ?? "",
    expandedVendorId ?? undefined,
  );
  const productDetail = useProductDetail(selectedProductId ?? undefined);

  function exitCustom() {
    onComplete({ isCustom: true, catalogueProductId: null, catalogueProductName: null });
  }

  function toggleCategory(id: string) {
    const next = expandedCategoryId === id ? null : id;
    setExpandedCategoryId(next);
    setExpandedSubcategoryId(null);
    setExpandedVendorId(null);
    vendorAutoSkipPrevented.current = false;
  }

  function toggleSubcategory(id: string) {
    const next = expandedSubcategoryId === id ? null : id;
    setExpandedSubcategoryId(next);
    setExpandedVendorId(null);
    vendorAutoSkipPrevented.current = false;
  }

  function toggleVendor(id: string) {
    setExpandedVendorId(expandedVendorId === id ? null : id);
  }

  // Auto-skip vendor rung when exactly one vendor in expanded sub-category.
  useEffect(() => {
    if (vendorAutoSkipPrevented.current) return;
    if (
      expandedSubcategoryId &&
      expandedVendorId === null &&
      vendors.data !== undefined &&
      vendors.data.length === 1
    ) {
      setExpandedVendorId(vendors.data[0].id);
    }
  }, [expandedSubcategoryId, expandedVendorId, vendors.data]);

  // ── Confirm stage ───────────────────────────────────────────────────────────
  if (selectedProductId) {
    if (productDetail.isLoading) return <Skeleton />;
    if (productDetail.isError || !productDetail.data) {
      return (
        <ErrorState
          message="Could not load this product."
          onRetry={() => productDetail.refetch()}
        />
      );
    }
    const product = productDetail.data;
    return (
      <PageScaffold>
        <PageHeader
          title="Confirm your product selection"
          onBack={() => setSelectedProductId(null)}
        />
        <div className="flex items-center gap-3">
          <LogoTile src={product.logo_url} name={product.name} />
          <div>
            <p className="font-semibold text-ink">{product.name}</p>
            <div className="mt-1 flex items-center gap-2">
              <LogoTile src={product.vendor.logo_url} name={product.vendor.name} size={24} />
              <span className="text-sm text-ink-muted">{product.vendor.name}</span>
            </div>
          </div>
        </div>
        <Button
          type="button"
          onClick={() =>
            onComplete({
              isCustom: false,
              catalogueProductId: product.id,
              catalogueProductName: product.name,
            })
          }
        >
          Use this product
        </Button>
      </PageScaffold>
    );
  }

  // ── Main accordion ──────────────────────────────────────────────────────────
  if (topCategories.isLoading) return <Skeleton />;
  if (topCategories.isError) {
    return (
      <ErrorState
        message="Could not load categories."
        onRetry={() => topCategories.refetch()}
      />
    );
  }

  const topList = topCategories.data ?? [];

  return (
    <PageScaffold>
      <section aria-label="category-drill-down" className="space-y-4">
        <PageHeader
          title="Select a product category"
          subtitle="Choose the category that best describes your AI product."
          onBack={exitCustom}
        />

        {topList.length === 0 ? (
          <EmptyState
            message="No categories available — use the option below to register a custom or in-house system."
            action={<InHouseExit onExit={exitCustom} />}
          />
        ) : (
          <>
            <ul className="space-y-2">
              {topList.map((cat) => {
                const isCatExpanded = expandedCategoryId === cat.id;

                // Build sub-category content for this category's branch children
                let catChildren: React.ReactNode = null;
                if (isCatExpanded) {
                  if (subCategories.isLoading) {
                    catChildren = <div className="mt-2 pl-4"><Skeleton /></div>;
                  } else if (subCategories.isError) {
                    catChildren = (
                      <div className="mt-2 pl-4">
                        <ErrorState
                          message="Could not load sub-categories."
                          onRetry={() => subCategories.refetch()}
                        />
                      </div>
                    );
                  } else {
                    const subList = subCategories.data ?? [];
                    const directProducts = categoryDirectProducts.data ?? [];

                    if (subList.length === 0 && directProducts.length === 0) {
                      catChildren = (
                        <div className="mt-2 pl-4">
                          <EmptyState
                            message="No products available in this category."
                            action={<InHouseExit onExit={exitCustom} />}
                          />
                        </div>
                      );
                    } else {
                      catChildren = (
                        <div className="mt-2 pl-4 space-y-2">
                          {/* Sub-category branch rows — single-open among siblings */}
                          {subList.length > 0 && (
                            <ul className="space-y-2">
                              {subList.map((sub) => {
                                const isSubExpanded = expandedSubcategoryId === sub.id;
                                const vendorList = vendors.data ?? [];
                                const showVendorLevel = vendorList.length > 1;

                                let subChildren: React.ReactNode = null;
                                if (isSubExpanded) {
                                  if (vendors.isLoading) {
                                    subChildren = <div className="mt-2 pl-4"><Skeleton /></div>;
                                  } else if (vendors.isError) {
                                    subChildren = (
                                      <div className="mt-2 pl-4">
                                        <ErrorState
                                          message="Could not load vendors."
                                          onRetry={() => vendors.refetch()}
                                        />
                                      </div>
                                    );
                                  } else if (vendorList.length === 0) {
                                    subChildren = (
                                      <div className="mt-2 pl-4">
                                        <EmptyState
                                          message="No vendors available in this category."
                                          action={<InHouseExit onExit={exitCustom} />}
                                        />
                                      </div>
                                    );
                                  } else if (showVendorLevel) {
                                    // Multi-vendor: show vendor branch rows
                                    subChildren = (
                                      <ul className="mt-2 pl-4 space-y-2">
                                        {vendorList.map((v) => {
                                          const isVendorExpanded = expandedVendorId === v.id;
                                          let vendorChildren: React.ReactNode = null;
                                          if (isVendorExpanded) {
                                            if (subCategoryProducts.isLoading) {
                                              vendorChildren = <div className="mt-2 pl-4"><Skeleton /></div>;
                                            } else if (subCategoryProducts.isError) {
                                              vendorChildren = (
                                                <div className="mt-2 pl-4">
                                                  <ErrorState
                                                    message="Could not load products."
                                                    onRetry={() => subCategoryProducts.refetch()}
                                                  />
                                                </div>
                                              );
                                            } else {
                                              const pList = subCategoryProducts.data ?? [];
                                              vendorChildren = pList.length === 0 ? (
                                                <div className="mt-2 pl-4">
                                                  <EmptyState
                                                    message="No products found."
                                                    action={<InHouseExit onExit={exitCustom} />}
                                                  />
                                                </div>
                                              ) : (
                                                <ul className="mt-2 pl-4 space-y-2">
                                                  {pList.map((p) => (
                                                    <li key={p.id}>
                                                      <ListSelectRow
                                                        label={p.name}
                                                        leading={<LogoTile src={p.logo_url} name={p.name} />}
                                                        onClick={() => setSelectedProductId(p.id)}
                                                      />
                                                    </li>
                                                  ))}
                                                </ul>
                                              );
                                            }
                                          }
                                          return (
                                            <li key={v.id}>
                                              <ListSelectRow
                                                label={v.name}
                                                leading={<LogoTile src={v.logo_url} name={v.name} />}
                                                onClick={() => {}}
                                                onToggle={() => toggleVendor(v.id)}
                                                expanded={isVendorExpanded}
                                              >
                                                {vendorChildren}
                                              </ListSelectRow>
                                            </li>
                                          );
                                        })}
                                      </ul>
                                    );
                                  } else {
                                    // Single vendor (auto-skip): show products once vendorId is
                                    // confirmed (prevents a transient flash before auto-skip fires)
                                    if (expandedVendorId === null || subCategoryProducts.isLoading) {
                                      subChildren = <div className="mt-2 pl-4"><Skeleton /></div>;
                                    } else if (subCategoryProducts.isError) {
                                      subChildren = (
                                        <div className="mt-2 pl-4">
                                          <ErrorState
                                            message="Could not load products."
                                            onRetry={() => subCategoryProducts.refetch()}
                                          />
                                        </div>
                                      );
                                    } else {
                                      const pList = subCategoryProducts.data ?? [];
                                      subChildren = pList.length === 0 ? (
                                        <div className="mt-2 pl-4">
                                          <EmptyState
                                            message="No products found."
                                            action={<InHouseExit onExit={exitCustom} />}
                                          />
                                        </div>
                                      ) : (
                                        <ul className="mt-2 pl-4 space-y-2">
                                          {pList.map((p) => (
                                            <li key={p.id}>
                                              <ListSelectRow
                                                label={p.name}
                                                leading={<LogoTile src={p.logo_url} name={p.name} />}
                                                onClick={() => setSelectedProductId(p.id)}
                                              />
                                            </li>
                                          ))}
                                        </ul>
                                      );
                                    }
                                  }

                                }

                                return (
                                  <li key={sub.id}>
                                    <ListSelectRow
                                      label={sub.name}
                                      onClick={() => {}}
                                      onToggle={() => toggleSubcategory(sub.id)}
                                      expanded={isSubExpanded}
                                    >
                                      {subChildren}
                                    </ListSelectRow>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          {/* Direct product leaf rows (mixed-node DF-C2-8) — always visible */}
                          {directProducts.length > 0 && (
                            <ul className="space-y-2">
                              {directProducts.map((p) => (
                                <li key={p.id}>
                                  <ListSelectRow
                                    label={p.name}
                                    leading={<LogoTile src={p.logo_url} name={p.name} />}
                                    onClick={() => setSelectedProductId(p.id)}
                                  />
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    }
                  }
                }

                return (
                  <li key={cat.id}>
                    <ListSelectRow
                      label={cat.name}
                      onClick={() => {}}
                      onToggle={() => toggleCategory(cat.id)}
                      expanded={isCatExpanded}
                    >
                      {catChildren}
                    </ListSelectRow>
                  </li>
                );
              })}
            </ul>
            <InHouseExit onExit={exitCustom} />
          </>
        )}
      </section>
    </PageScaffold>
  );
}
