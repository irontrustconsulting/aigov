"use client";

import { useState } from "react";
import { Button } from "@irontrust/ui";
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

/**
 * WI-4: top-level category → sub-category → products → confirm.
 * Products live on sub-categories, not top-level, so two levels of
 * category selection are required before products appear.
 * "Not in catalogue / in-house" exits from any level.
 */
export function DrillDownStep({ onComplete }: { onComplete: (result: DrillDownResult) => void }) {
  // topLevelId: the selected top-level category (null = stage 1)
  // subCategoryId: the selected sub-category (null = stage 1/2, set = stage 3)
  const [topLevelId, setTopLevelId] = useState<string | null>(null);
  const [subCategoryId, setSubCategoryId] = useState<string | null>(null);
  const [vendorId, setVendorId] = useState<string | undefined>(undefined);
  const [productId, setProductId] = useState<string | null>(null);

  const topCategories = useProductCategories();
  const subCategories = useProductCategories(topLevelId ?? undefined);
  const vendors = useVendorsInCategory(subCategoryId ?? "");
  const products = useProductsInCategory(subCategoryId ?? "", vendorId);
  const productDetail = useProductDetail(productId ?? undefined);

  function exitCustom() {
    onComplete({ isCustom: true, catalogueProductId: null, catalogueProductName: null });
  }

  // -------------------------------------------------------------------
  // Stage 4: product detail confirmation
  // -------------------------------------------------------------------
  if (productId) {
    if (productDetail.isLoading) return <p>Loading product…</p>;
    if (productDetail.isError || !productDetail.data) {
      return <p role="alert">Could not load this product.</p>;
    }
    const product = productDetail.data;
    return (
      <section aria-label="product-confirm" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
        <h2 className="text-lg font-semibold">{product.name}</h2>
        <p className="text-ink-muted text-sm">Vendor: {product.vendor.name}</p>
        {product.categories.length > 0 && (
          <p className="text-ink-muted text-sm">
            Categories: {product.categories.map((c) => c.name).join(", ")}
          </p>
        )}
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
      </section>
    );
  }

  // -------------------------------------------------------------------
  // Stage 3: products within the chosen sub-category
  // -------------------------------------------------------------------
  if (subCategoryId) {
    const vendorList = vendors.data ?? [];
    const productList = products.data ?? [];
    const selectedVendorName = vendorList.find((v) => v.id === vendorId)?.name;

    return (
      <section aria-label="vendor-product-browse" className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        <Button
          type="button"
          variant="secondary"
          onClick={() => { setSubCategoryId(null); setVendorId(undefined); }}
        >
          ← Back
        </Button>

        {vendorList.length > 1 && (
          <div>
            <p className="text-ink-muted mb-2 text-sm font-medium">Filter by vendor</p>
            <div className="flex flex-wrap gap-2">
              {vendorList.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  aria-pressed={vendorId === v.id}
                  className={`border-hairline rounded-full border px-3 py-1 text-sm transition-colors ${
                    vendorId === v.id ? "bg-ink text-surface" : "hover:bg-surface-sunken"
                  }`}
                  onClick={() => setVendorId(vendorId === v.id ? undefined : v.id)}
                >
                  {v.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <p className="text-ink-muted mb-2 text-sm font-medium">
            {selectedVendorName ? `Products by ${selectedVendorName}` : "Products"}
          </p>
          {(products.isLoading || vendors.isLoading) && <p>Loading…</p>}
          {!products.isLoading && productList.length === 0 && (
            <p className="text-ink-muted text-sm">No products found in this category.</p>
          )}
          {productList.length > 0 && (
            <ul className="space-y-2">
              {productList.map((p) => {
                const vendor = vendorList.find((v) => v.id === p.vendor_id);
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="border-hairline hover:bg-surface-sunken w-full rounded-lg border px-4 py-3 text-left"
                      onClick={() => setProductId(p.id)}
                    >
                      <span className="font-medium">{p.name}</span>
                      {vendor && (
                        <span className="text-ink-muted ml-2 text-sm">{vendor.name}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <Button type="button" variant="secondary" onClick={exitCustom}>
          Not in catalogue / in-house
        </Button>
      </section>
    );
  }

  // -------------------------------------------------------------------
  // Stage 2: sub-categories of the chosen top-level category
  // -------------------------------------------------------------------
  if (topLevelId) {
    return (
      <section aria-label="sub-category-list" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
        <Button type="button" variant="secondary" onClick={() => setTopLevelId(null)}>
          ← Back
        </Button>
        <h2 className="text-lg font-semibold">Select a sub-category</h2>

        {subCategories.isLoading && <p>Loading…</p>}
        {subCategories.isError && <p role="alert">Could not load categories.</p>}
        {subCategories.data && subCategories.data.length === 0 && (
          <p className="text-ink-muted text-sm">No sub-categories available here.</p>
        )}

        {subCategories.data && subCategories.data.length > 0 && (
          <ul className="space-y-2">
            {subCategories.data.map((cat) => (
              <li key={cat.id}>
                <button
                  type="button"
                  className="border-hairline hover:bg-surface-sunken w-full rounded-lg border px-4 py-3 text-left"
                  onClick={() => setSubCategoryId(cat.id)}
                >
                  <span className="font-medium">{cat.name}</span>
                  {cat.description && (
                    <span className="text-ink-muted mt-0.5 block text-sm">{cat.description}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}

        <Button type="button" variant="secondary" onClick={exitCustom}>
          Not in catalogue / in-house
        </Button>
      </section>
    );
  }

  // -------------------------------------------------------------------
  // Stage 1: top-level categories
  // -------------------------------------------------------------------
  return (
    <section aria-label="category-drill-down" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <h2 className="text-lg font-semibold">Select a product category</h2>
      <p className="text-ink-muted text-sm">
        Choose the category that best describes your AI product.
      </p>

      {topCategories.isLoading && <p>Loading…</p>}
      {topCategories.isError && <p role="alert">Could not load categories.</p>}
      {topCategories.data && topCategories.data.length === 0 && (
        <p className="text-ink-muted text-sm" aria-label="no-categories">
          No categories available — use the option below to register a custom or in-house system.
        </p>
      )}

      {topCategories.data && topCategories.data.length > 0 && (
        <ul className="space-y-2">
          {topCategories.data.map((cat) => (
            <li key={cat.id}>
              <button
                type="button"
                className="border-hairline hover:bg-surface-sunken w-full rounded-lg border px-4 py-3 text-left"
                onClick={() => setTopLevelId(cat.id)}
              >
                <span className="font-medium">{cat.name}</span>
                {cat.description && (
                  <span className="text-ink-muted mt-0.5 block text-sm">{cat.description}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Button type="button" variant="secondary" onClick={exitCustom}>
        Not in catalogue / in-house
      </Button>
    </section>
  );
}
