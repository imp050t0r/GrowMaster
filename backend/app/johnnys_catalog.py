"""Compatibility bridge for GrowMaster 1.24.x.

The default supplier catalogue is EU-first. This module remains only so older
imports keep working while the seed database migrates without breaking existing
user lots, plans, reservations or history.
"""

from app.eu_seed_catalog import EU_SEED_CATALOG

JOHNNYS_SLOVENIA_VARIETIES = EU_SEED_CATALOG
