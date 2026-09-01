"""EU-first seed catalogue compatibility bridge for GrowMaster 1.24.x.

EU/SI supplier data is applied first. The former Johnny's catalogue is kept only
as a secondary agronomic fallback so existing profiles and old user records keep
working. Purchasing guidance must prefer the EU entries.
"""

from app.eu_seed_catalog import EU_SEED_CATALOG
from app.eu_chard_crops import EU_CHARD_CROPS
from app.eu_leafy_crops import EU_LEAFY_CROPS
from app.legacy_johnnys_catalog import (
    JOHNNYS_SLOVENIA_VARIETIES as LEGACY_AGRONOMIC_REFERENCE,
)
from app.professional_completion_catalog import PROFESSIONAL_COMPLETION_CATALOG

JOHNNYS_SLOVENIA_VARIETIES = (
    EU_SEED_CATALOG
    + EU_CHARD_CROPS
    + EU_LEAFY_CROPS
    + PROFESSIONAL_COMPLETION_CATALOG
    + LEGACY_AGRONOMIC_REFERENCE
)
