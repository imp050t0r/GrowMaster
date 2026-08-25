import app.main as main_module
from app.agronomy_admin_routes import router as agronomy_admin_router
from app.master_data_routes import router as master_data_router
from app.seed_actuals_routes import router as seed_actuals_router
from app.seed_forecast_routes import router as seed_forecast_router
from app.seed_inventory_link import register_seed_inventory_hooks
from app.seed_inventory_routes import router as seed_inventory_router
from app.seed_ops_routes import router as seed_ops_router
from app.seed_purchase_routes import router as seed_purchase_router
from app.seed_quantity_routes import router as seed_quantity_router
from app.seeding_data_routes import router as seeding_data_router
from app.successor_routes import router as successor_router


APP_VERSION = "1.23.0"
main_module.APP_VERSION = APP_VERSION
app = main_module.app
app.version = APP_VERSION

register_seed_inventory_hooks()

app.include_router(successor_router)
app.include_router(master_data_router)
app.include_router(seeding_data_router)
app.include_router(seed_quantity_router)
app.include_router(seed_inventory_router)
app.include_router(seed_forecast_router)
app.include_router(seed_ops_router)
app.include_router(seed_purchase_router)
app.include_router(seed_actuals_router)
app.include_router(agronomy_admin_router)
