"""
Seed the global catalogue: vendors -> products -> (facts, product-risks).

The catalogue is global reference data (cross-tenant, the moat). One YAML
holds the chain, nested by ownership:

    - name: Adobe
      last_verified_at: null
      products:
        - name: Firefly
          taxonomy_tags: ["image_generation"]
          facts:
            - key: data_residency
              value: {region: "EU"}
              source_label: "Adobe DPA"
              provenance: catalogue_curated
          risks:                 # links to Risk by code
            - LLM05

Order matters within the chain, so this loader handles it explicitly rather
than via the generic runner: a product needs its vendor's id; a fact needs its
product's id; a product-risk link needs both the product and the risk.

Idempotency: vendors keyed on name, products on (vendor_id, name); facts and
risk-links are reconciled (cleared and recreated from the YAML) per product.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CatalogueVendor, CatalogueProduct, CatalogueFact, CatalogueProductRisk, Risk,
)
from app.models.base import ProvenanceConfidence
from scripts.seed.common import load_yaml, make_engine


def _get_or_create_vendor(session: Session, raw: dict) -> CatalogueVendor:
    vendor = session.scalar(
        select(CatalogueVendor).where(CatalogueVendor.name == raw["name"])
    )
    if vendor is None:
        vendor = CatalogueVendor(name=raw["name"], last_verified_at=raw.get("last_verified_at"))
        session.add(vendor)
        session.flush()  # get vendor.id
    else:
        vendor.last_verified_at = raw.get("last_verified_at")
    return vendor


def _get_or_create_product(session: Session, vendor: CatalogueVendor, raw: dict) -> CatalogueProduct:
    product = session.scalar(
        select(CatalogueProduct).where(
            CatalogueProduct.vendor_id == vendor.id,
            CatalogueProduct.name == raw["name"],
        )
    )
    if product is None:
        product = CatalogueProduct(
            vendor_id=vendor.id,
            name=raw["name"],
            taxonomy_tags=raw.get("taxonomy_tags", []),
            last_verified_at=raw.get("last_verified_at"),
        )
        session.add(product)
        session.flush()
    else:
        product.taxonomy_tags = raw.get("taxonomy_tags", [])
        product.last_verified_at = raw.get("last_verified_at")
    return product


def _reconcile_facts(session: Session, product: CatalogueProduct, facts: list[dict]) -> None:
    for existing in list(product.facts):
        session.delete(existing)
    session.flush()
    for f in facts:
        session.add(CatalogueFact(
            product_id=product.id,
            key=f["key"],
            value=f["value"],
            source_url=f.get("source_url"),
            source_label=f.get("source_label"),
            last_checked_at=f.get("last_checked_at"),
            provenance=ProvenanceConfidence(f.get("provenance", "catalogue_curated")),
        ))


def _reconcile_product_risks(session: Session, product: CatalogueProduct, risk_codes: list[str]) -> None:
    for existing in list(product.typical_risks):
        session.delete(existing)
    session.flush()
    for code in risk_codes:
        risk = session.scalar(select(Risk).where(Risk.code == code))
        if risk is None:
            raise RuntimeError(
                f"risk '{code}' (referenced by product '{product.name}') not found "
                f"— seed risks before the catalogue"
            )
        session.add(CatalogueProductRisk(product_id=product.id, risk_id=risk.id))


def main(session: Session | None = None) -> None:
    entries = load_yaml("catalogue.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        n_vendors = n_products = 0
        for v_raw in entries:
            vendor = _get_or_create_vendor(session, v_raw)
            n_vendors += 1
            for p_raw in v_raw.get("products", []):
                product = _get_or_create_product(session, vendor, p_raw)
                n_products += 1
                _reconcile_facts(session, product, p_raw.get("facts", []))
                _reconcile_product_risks(session, product, p_raw.get("risks", []))
        if own:
            session.commit()
        print(f"  catalogue: {n_vendors} vendors, {n_products} products processed")
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()