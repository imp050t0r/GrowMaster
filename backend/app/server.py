from app.main import app
from app.successor_routes import router as successor_router


app.include_router(successor_router)
