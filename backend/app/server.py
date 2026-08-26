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
from app.seeding_data_routes import router as seeding_data_router
from app.successor_routes import router as successor_router


APP_VERSION = "1.24.8"
main_module.APP_VERSION = APP_VERSION
app = main_module.app
app.version = APP_VERSION

# License endpoints must remain reachable before login and after trial expiry.
main_module.PUBLIC_API_PATHS.update({"/api/license/status", "/api/license/activate"})

LICENSE_WRITE_EXEMPT = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/setup",
    "/api/auth/mobile-session",
    "/api/license/activate",
}


@app.middleware("http")
async def license_access_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api/")
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and path not in LICENSE_WRITE_EXEMPT
    ):
        license_info = license_status()
        if not license_info["write_access"]:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "code": "license_required",
                        "message": "Preizkusna licenca je potekla. Za spremembe aktiviraj GrowMaster Pro.",
                        "license": license_info,
                    }
                },
            )
    return await call_next(request)


register_seed_inventory_hooks(app)
app.include_router(seed_inventory_router)
app.include_router(seed_forecast_router)
app.include_router(seed_purchase_router)
app.include_router(seed_ops_router)
app.include_router(seed_actuals_router)
app.include_router(seed_quantity_router)
app.include_router(seeding_data_router)
app.include_router(master_data_router)
app.include_router(agronomy_admin_router)
app.include_router(plant_db_router)
app.include_router(license_router)
app.include_router(successor_router)
app.include_router(backup_router)
