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
 * WI-4: category list -> vendor/product browse -> product detail confirm.
 * "Not in catalogue / in-house" is always reachable (CAT-8 miss signal
 * is out of F1 scope — no event emitted here).
 */
export function DrillDownStep({ onComplete }: { onComplete: (result: DrillDownResult) => void }) {
  const [browsingCategoryId, setBrowsingCategoryId] = useState<string | null>(null);
  const [vendorId, setVendorId] = useState<string | undefined>(undefined);
  const [productId, setProductId] = useState<string | null>(null);

  const categories = useProductCategories();
  const vendors = useVendorsInCategory(browsingCategoryId ?? "");
  const products = useProductsInCategory(browsingCategoryId ?? "", vendorId);
  const productDetail = useProductDetail(productId ?? undefined);

  function exitCustom() {
    onComplete({ isCustom: true, catalogueProductId: null, catalogueProductName: null });
  }

  function backToCategories() {
    setBrowsingCategoryId(null);
    setVendorId(undefined);
    setProductId(null);
  }

  // -------------------------------------------------------------------
  // Product detail confirmation
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
          <p className="text-ink-muted text-sm">Categories: {product.categories.map((c) => c.name).join(", ")}</p>
        )}
        <Button type="button" onClick={() => setProductId(null)} variant="secondary">
          Back
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
      </section>
    );
  }

  // -------------------------------------------------------------------
  // Vendor / product browsing within a chosen category
  // -------------------------------------------------------------------
  if (browsingCategoryId) {
    const vendorList = vendors.data ?? [];
    const productList = products.data ?? [];
    const selectedVendorName = vendorList.find((v) => v.id === vendorId)?.name;

    return (
      <section aria-label="vendor-product-browse" className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        <Button type="button" variant="secondary" onClick={backToCategories}>
          ← Back to categories
        </Button>

        {/* Vendor filter — only shown when there are multiple vendors */}
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
                    vendorId === v.id
                      ? "bg-ink text-surface"
                      : "hover:bg-surface-sunken"
                  }`}
                  onClick={() => setVendorId(vendorId === v.id ? undefined : v.id)}
                >
                  {v.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Product list */}
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
  // Category list — clicking goes directly to vendor/product browse
  // -------------------------------------------------------------------
  return (
    <section aria-label="category-drill-down" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <h2 className="text-lg font-semibold">Select a product category</h2>
      <p className="text-ink-muted text-sm">
        Choose the category that best describes your AI product.
      </p>

      {categories.isLoading && <p>Loading categories…</p>}
      {categories.isError && <p role="alert">Could not load categories.</p>}
      {categories.data && categories.data.length === 0 && (
        <p className="text-ink-muted text-sm">
          No categories available — use the option below to register a custom or in-house system.
        </p>
      )}

      {categories.data && categories.data.length > 0 && (
        <ul className="space-y-2">
          {categories.data.map((cat) => (
            <li key={cat.id}>
              <button
                type="button"
                className="border-hairline hover:bg-surface-sunken w-full rounded-lg border px-4 py-3 text-left"
                onClick={() => setBrowsingCategoryId(cat.id)}
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
