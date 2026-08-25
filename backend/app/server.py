from app.main import app
from app.master_data_routes import router as master_data_router
from app.seed_inventory_routes import router as seed_inventory_router
from app.seed_quantity_routes import router as seed_quantity_router
from app.seeding_data_routes import router as seeding_data_router
from app.successor_routes import router as successor_router


app.include_router(successor_router)
app.include_router(master_data_router)
app.include_router(seeding_data_router)
app.include_router(seed_quantity_router)
app.include_router(seed_inventory_router)
