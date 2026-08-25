from app.main import app
from app.master_data_routes import router as master_data_router
from app.successor_routes import router as successor_router


app.include_router(successor_router)
app.include_router(master_data_router)
