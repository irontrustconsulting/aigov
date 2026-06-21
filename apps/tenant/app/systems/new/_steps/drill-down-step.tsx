"use client";

import { useState } from "react";
import { Button, Table, TableRow, TableCell } from "@irontrust/ui";
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

interface Crumb {
  id: string | undefined;
  name: string;
}

/**
 * WI-4: category tree (parent_id drill) -> vendors -> products -> product
 * detail. "Not in catalogue / in-house" is always reachable and sets
 * is_custom, skipping straight to WI-5 with no product selected (CAT-8
 * catalogue-miss curation signal is explicitly out of F1 scope — no event
 * is emitted here).
 */
export function DrillDownStep({ onComplete }: { onComplete: (result: DrillDownResult) => void }) {
  const [breadcrumb, setBreadcrumb] = useState<Crumb[]>([{ id: undefined, name: "All categories" }]);
  const [browsingCategoryId, setBrowsingCategoryId] = useState<string | null>(null);
  const [vendorId, setVendorId] = useState<string | undefined>(undefined);
  const [productId, setProductId] = useState<string | null>(null);

  const currentParentId = breadcrumb[breadcrumb.length - 1]?.id;
  const categories = useProductCategories(browsingCategoryId ? undefined : currentParentId);
  const vendors = useVendorsInCategory(browsingCategoryId ?? "");
  const products = useProductsInCategory(browsingCategoryId ?? "", vendorId);
  const productDetail = useProductDetail(productId ?? undefined);

  function exitCustom() {
    onComplete({ isCustom: true, catalogueProductId: null, catalogueProductName: null });
  }

  function chooseCategory(id: string, name: string) {
    setBreadcrumb((prev) => [...prev, { id, name }]);
  }

  function backOneLevel() {
    if (browsingCategoryId) {
      setBrowsingCategoryId(null);
      setVendorId(undefined);
      setProductId(null);
      return;
    }
    setBreadcrumb((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev));
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
      <section aria-label="product-confirm">
        <h2>{product.name}</h2>
        <p>Vendor: {product.vendor.name}</p>
        {product.categories.length > 0 && (
          <p>Categories: {product.categories.map((c) => c.name).join(", ")}</p>
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
    return (
      <section aria-label="vendor-product-browse">
        <Button type="button" variant="secondary" onClick={backOneLevel}>
          Back to categories
        </Button>

        <h3>Vendors</h3>
        {vendors.isLoading && <p>Loading vendors…</p>}
        {vendors.data && vendors.data.length === 0 && <p>No vendors in this category yet.</p>}
        <Table>
          {vendors.data?.map((v) => (
            <TableRow key={v.id}>
              <TableCell>
                <button
                  type="button"
                  aria-pressed={vendorId === v.id}
                  onClick={() => setVendorId(vendorId === v.id ? undefined : v.id)}
                >
                  {v.name}
                </button>
              </TableCell>
            </TableRow>
          ))}
        </Table>

        <h3>Products</h3>
        {products.isLoading && <p>Loading products…</p>}
        {products.data && products.data.length === 0 && <p>No products found.</p>}
        <Table>
          {products.data?.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <button type="button" onClick={() => setProductId(p.id)}>
                  {p.name}
                </button>
              </TableCell>
            </TableRow>
          ))}
        </Table>

        <Button type="button" variant="secondary" onClick={exitCustom}>
          Not in catalogue / in-house
        </Button>
      </section>
    );
  }

  // -------------------------------------------------------------------
  // Category tree
  // -------------------------------------------------------------------
  return (
    <section aria-label="category-drill-down">
      <nav aria-label="breadcrumb">
        {breadcrumb.map((c, i) => (
          <span key={c.id ?? "root"}>
            {i > 0 && " / "}
            {c.name}
          </span>
        ))}
      </nav>

      {breadcrumb.length > 1 && (
        <Button type="button" variant="secondary" onClick={backOneLevel}>
          Back
        </Button>
      )}

      {categories.isLoading && <p>Loading categories…</p>}
      {categories.isError && <p role="alert">Could not load categories.</p>}
      {categories.data && categories.data.length === 0 && (
        <p>No categories here — browse vendors and products directly, or use the exit below.</p>
      )}

      <Table>
        {categories.data?.map((cat) => (
          <TableRow key={cat.id}>
            <TableCell>
              <button type="button" onClick={() => chooseCategory(cat.id, cat.name)}>
                {cat.name}
              </button>
            </TableCell>
            <TableCell>
              <button type="button" onClick={() => setBrowsingCategoryId(cat.id)}>
                Browse vendors/products
              </button>
            </TableCell>
          </TableRow>
        ))}
      </Table>

      <Button type="button" variant="secondary" onClick={exitCustom}>
        Not in catalogue / in-house
      </Button>
    </section>
  );
}
