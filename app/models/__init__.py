"""
Import all models here so that Base.metadata is fully populated for
Alembic autogenerate and for `Base.metadata.create_all` in tests.

    from models import Base
    target_metadata = Base.metadata   # in alembic/env.py
"""

from .base import Base, UserRole, SystemLifecycleStage  # noqa: F401

# Identity & tenancy
from .identity import Tenant, User, Membership  # noqa: F401

# Core domain
from .domain import (  # noqa: F401
    CatalogueVendor, CatalogueProduct, CatalogueFact, CatalogueProductRisk,
    System, UseCase, VendorApproval, ProductApproval,
)

# Knowledge assets
from .knowledge import (  # noqa: F401
    Control, ControlFrameworkMap, Risk, RiskControlMap,
)

# Assessment
from .assessment import (  # noqa: F401
    Classification, Assessment, AssessmentItem,
    AssessmentItemControl, AssessmentItemEvidence, AssessmentSectionTemplate,
)

# Evidence, audit, lifecycle
from .lifecycle import (  # noqa: F401
    Evidence, AuditEvent, LifecycleTransition,
)

from app.models.taxonomy import (  # noqa: F401
    EUAIActCategory, EUAIActSubcategory, ProductCategory,
    ProductCategoryMembership, ProductCategoryEUMapping,
)

from app.models.platform_rbac import (
    Operator, Permission, Role, RolePermission, OperatorRole
)

from app.models.platform_audit import PlatformAuditEvent  # noqa: F401

# Tenant governance roles (catalogue, SoD matrix, assignments)
from app.models.governance import (  # noqa: F401
    GovernanceRole, GovernanceRoleConflict, GovernanceRoleAssignment,
)

# System Intake vocab and link tables
from app.models.intake import (  # noqa: F401
    EUOperatorRole, HostingModel, UsageContext, HumanOversightType,
    DataCategory, AffectedParty,
    SystemDataCategory, SystemAffectedParty,
)

# Classification gate — decision tree reference tables (global, no RLS)
from app.models.decision_tree import (  # noqa: F401
    DecisionTree, DecisionTreeQuestion, DecisionTreeOption,
)