"""EU-first seed catalogue compatibility bridge for GrowMaster 1.24.x.

EU/SI supplier data is applied first. The former Johnny's catalogue is kept only
as a secondary agronomic fallback so existing profiles and old user records keep
working. Purchasing guidance must prefer the EU entries.
"""

from app.eu_seed_catalog import EU_SEED_CATALOG
from app.legacy_johnnys_catalog import (
    JOHNNYS_SLOVENIA_VARIETIES as LEGACY_AGRONOMIC_REFERENCE,
)

JOHNNYS_SLOVENIA_VARIETIES = EU_SEED_CATALOG + LEGACY_AGRONOMIC_REFERENCE
