from fastapi import Request, status
from fastapi.responses import JSONResponse

import app.main as main_module
from app.agronomy_admin_routes import router as agronomy_admin_router
from app.backup_routes import router as backup_router
from app.license_routes import router as license_router
from app.license_service import status as license_status
from app.master_data_routes import router as master_data_router
from app.plant_db_routes import router as plant_db_router
from app.seed_actuals_routes import router as seed_actuals_router
from app.seed_forecast_routes import router as seed_forecast_router
from app.seed_inventory_link import register_seed_inventory_hooks
from app.seed_inventory_routes import router as seed_inventory_router
from app.seed_ops_routes import router as seed_ops_router
from app.seed_purchase_routes import router as seed_purchase_router
from app.seed_quantity_routes import router as seed_quantity_router
from app.seed_supplier_search_routes import router as seed_supplier_search_router
from app.seeding_data_routes import router as seeding_data_router
from app.successor_routes import router as successor_router


APP_VERSION = "1.24.25"
main_module.APP_VERSION = APP_VERSION
app = main_module.app
app.version = APP_VERSION

# License endpoints must remain reachable before login and after trial expiry.
main_module.PUBLIC_API_PATHS.update({"/api/license/status", "/api/license/activate"})

LICENSE_WRITE_EXEMPT = {
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/license/activate",
}
ADMIN_WRITE_PATHS = {
    "/api/system/master-data/export",
    "/api/system/master-data/reload",
    "/api/system/seeding-data/export",
    "/api/system/plant-db/initialize",
    "/api/system/plant-db/reload",
    "/api/system/backups/restore",
    "/api/master-data/backfill-seeding",
    "/api/agronomy/learning/apply",
}


@app.middleware("http")
async def enforce_growmaster_license(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)

    current = license_status()
    is_write = request.method not in {"GET", "HEAD", "OPTIONS"}

    if is_write and path in ADMIN_WRITE_PATHS and not current["admin_access"]:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Ta funkcija je na voljo samo z GrowMaster Admin licenco.",
                "license": current,
            },
            headers={"Cache-Control": "no-store"},
        )

    if is_write and path not in LICENSE_WRITE_EXEMPT and not current["full_access"]:
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={
                "detail": "30-dnevno testno obdobje je poteklo. Aktiviraj GrowMaster Pro za nadaljnje spremembe podatkov.",
                "license": current,
            },
            headers={"Cache-Control": "no-store"},
        )
    return await call_next(request)


register_seed_inventory_hooks()

app.include_router(license_router)
app.include_router(successor_router)
app.include_router(master_data_router)
app.include_router(plant_db_router)
app.include_router(backup_router)
app.include_router(seeding_data_router)
app.include_router(seed_quantity_router)
app.include_router(seed_inventory_router)
app.include_router(seed_forecast_router)
app.include_router(seed_ops_router)
app.include_router(seed_purchase_router)
app.include_router(seed_supplier_search_router)
app.include_router(seed_actuals_router)
app.include_router(agronomy_admin_router)
