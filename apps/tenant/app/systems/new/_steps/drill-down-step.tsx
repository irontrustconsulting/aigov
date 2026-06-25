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
 * WI-4 (D-56): top-level category → sub-category → vendor rung (auto-skip
 * when exactly 1 vendor) → product → confirm. ListSelectRow + LogoTile on
 * vendor and product rungs; no tile on category rungs. Four INV-70 states per
 * rung. In-house exit at every rung. DrillDownResult shape unchanged.
 */
export function DrillDownStep({ onComplete }: { onComplete: (result: DrillDownResult) => void }) {
  const [topLevelId, setTopLevelId] = useState<string | null>(null);
  const [subCategoryId, setSubCategoryId] = useState<string | null>(null);
  const [vendorId, setVendorId] = useState<string | null>(null);
  const [productId, setProductId] = useState<string | null>(null);

  // Prevents re-triggering vendor auto-skip when user explicitly navigates back
  // from the product rung after a single-vendor skip.
  const vendorAutoSkipPrevented = useRef(false);

  const topCategories = useProductCategories();
  const subCategories = useProductCategories(topLevelId ?? undefined);
  const vendors = useVendorsInCategory(subCategoryId ?? "");
  const products = useProductsInCategory(subCategoryId ?? "", vendorId ?? undefined);
  const productDetail = useProductDetail(productId ?? undefined);

  function exitCustom() {
    onComplete({ isCustom: true, catalogueProductId: null, catalogueProductName: null });
  }

  function selectSubCategory(id: string) {
    vendorAutoSkipPrevented.current = false;
    setSubCategoryId(id);
    setVendorId(null);
    setProductId(null);
  }

  function goBackFromProductRung() {
    if (vendors.data?.length === 1) {
      vendorAutoSkipPrevented.current = true;
    }
    setVendorId(null);
    setProductId(null);
  }

  // Auto-skip vendor rung when there is exactly one vendor.
  useEffect(() => {
    if (vendorAutoSkipPrevented.current) return;
    if (
      subCategoryId &&
      vendorId === null &&
      productId === null &&
      vendors.data !== undefined &&
      vendors.data.length === 1
    ) {
      setVendorId(vendors.data[0].id);
    }
  }, [subCategoryId, vendorId, productId, vendors.data]);

  // ── Stage 4: confirm ────────────────────────────────────────────────────────
  if (productId) {
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
        <PageHeader title="Confirm your product selection" />
        <div className="flex items-center gap-3">
          <LogoTile src={product.logo_url} name={product.name} />
          <div>
            <p className="font-semibold text-ink">{product.name}</p>
            {product.vendor && (
              <div className="mt-1 flex items-center gap-2">
                <LogoTile src={product.vendor.logo_url} name={product.vendor.name} size={24} />
                <span className="text-sm text-ink-muted">{product.vendor.name}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button type="button" onClick={() => setProductId(null)} variant="secondary">
            ← Back
          </Button>
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
        </div>
      </PageScaffold>
    );
  }

  // ── Stage 3b: product rung ──────────────────────────────────────────────────
  if (subCategoryId && vendorId !== null) {
    if (products.isLoading) return <Skeleton />;
    if (products.isError) {
      return (
        <ErrorState
          message="Could not load products."
          onRetry={() => products.refetch()}
        />
      );
    }
    const productList = products.data ?? [];
    return (
      <PageScaffold>
        <PageHeader title="Select a product" />
        <Button type="button" variant="secondary" onClick={goBackFromProductRung}>
          ← Back
        </Button>
        {productList.length === 0 ? (
          <EmptyState
            message="No products found in this category."
            action={<InHouseExit onExit={exitCustom} />}
          />
        ) : (
          <>
            <ul className="space-y-2" aria-label="vendor-product-browse">
              {productList.map((p) => (
                <li key={p.id}>
                  <ListSelectRow
                    label={p.name}
                    leading={<LogoTile src={p.logo_url} name={p.name} />}
                    onClick={() => setProductId(p.id)}
                  />
                </li>
              ))}
            </ul>
            <InHouseExit onExit={exitCustom} />
          </>
        )}
      </PageScaffold>
    );
  }

  // ── Stage 3a: vendor rung ───────────────────────────────────────────────────
  if (subCategoryId) {
    if (vendors.isLoading) return <Skeleton />;
    if (vendors.isError) {
      return (
        <ErrorState
          message="Could not load vendors."
          onRetry={() => vendors.refetch()}
        />
      );
    }
    const vendorList = vendors.data ?? [];
    return (
      <PageScaffold>
        <PageHeader title="Select a vendor" />
        <Button
          type="button"
          variant="secondary"
          onClick={() => { setSubCategoryId(null); setVendorId(null); }}
        >
          ← Back
        </Button>
        {vendorList.length === 0 ? (
          <EmptyState
            message="No vendors available in this category."
            action={<InHouseExit onExit={exitCustom} />}
          />
        ) : (
          <>
            <ul className="space-y-2" aria-label="vendor-list">
              {vendorList.map((v) => (
                <li key={v.id}>
                  <ListSelectRow
                    label={v.name}
                    leading={<LogoTile src={v.logo_url} name={v.name} />}
                    onClick={() => setVendorId(v.id)}
                  />
                </li>
              ))}
            </ul>
            <InHouseExit onExit={exitCustom} />
          </>
        )}
      </PageScaffold>
    );
  }

  // ── Stage 2: sub-category rung ──────────────────────────────────────────────
  if (topLevelId) {
    if (subCategories.isLoading) return <Skeleton />;
    if (subCategories.isError) {
      return (
        <ErrorState
          message="Could not load categories."
          onRetry={() => subCategories.refetch()}
        />
      );
    }
    const subList = subCategories.data ?? [];
    return (
      <PageScaffold>
        <PageHeader title="Select a sub-category" />
        <Button type="button" variant="secondary" onClick={() => setTopLevelId(null)}>
          ← Back
        </Button>
        {subList.length === 0 ? (
          <EmptyState
            message="No sub-categories available here."
            action={<InHouseExit onExit={exitCustom} />}
          />
        ) : (
          <>
            <ul className="space-y-2" aria-label="sub-category-list">
              {subList.map((cat) => (
                <li key={cat.id}>
                  <ListSelectRow
                    label={cat.name}
                    onClick={() => selectSubCategory(cat.id)}
                  />
                </li>
              ))}
            </ul>
            <InHouseExit onExit={exitCustom} />
          </>
        )}
      </PageScaffold>
    );
  }

  // ── Stage 1: top-level categories ──────────────────────────────────────────
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
        />
        {topList.length === 0 ? (
          <EmptyState
            message="No categories available — use the option below to register a custom or in-house system."
            action={<InHouseExit onExit={exitCustom} />}
          />
        ) : (
          <>
            <ul className="space-y-2">
              {topList.map((cat) => (
                <li key={cat.id}>
                  <ListSelectRow
                    label={cat.name}
                    onClick={() => setTopLevelId(cat.id)}
                  />
                </li>
              ))}
            </ul>
            <InHouseExit onExit={exitCustom} />
          </>
        )}
      </section>
    </PageScaffold>
  );
}
