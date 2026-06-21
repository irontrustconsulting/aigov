/** app/schemas/reference.py + the WI-0 vocab-list additions
 * (app/schemas/system.py: VocabItemOut/DataCategoryOut/AffectedPartyOut). */
import type { EUAIActTier } from "./enums";

export interface ProductCategoryRead {
  id: string;
  code: string;
  name: string;
  description: string | null;
  parent_id: string | null;
}

export interface VendorRead {
  id: string;
  name: string;
  logo_url: string | null;
}

export interface ProductRead {
  id: string;
  name: string;
  vendor_id: string;
  logo_url: string | null;
}

export interface EUAIActSubcategoryRead {
  id: string;
  code: string;
  name: string;
  description: string | null;
  category_id: string;
  tier: EUAIActTier;
}

export interface CatalogueVendorRef {
  id: string;
  name: string;
}

export interface CategoryRef {
  id: string;
  name: string;
}

export interface EUAIActSubcategoryRef {
  id: string;
  code: string;
  label: string;
}

export interface ProductDetailOut {
  id: string;
  name: string;
  vendor: CatalogueVendorRef;
  categories: CategoryRef[];
  eu_ai_act_subcategories: EUAIActSubcategoryRef[];
}

/** app/schemas/system.py VocabItemOut — shared shape for the four
 * single-select intake-vocab lists (WI-0). */
export interface VocabItemOut {
  id: string;
  code: string;
  label: string;
}

export interface DataCategoryOut extends VocabItemOut {
  is_special_category: boolean;
}

export interface AffectedPartyOut extends VocabItemOut {
  is_vulnerable_group: boolean;
}
