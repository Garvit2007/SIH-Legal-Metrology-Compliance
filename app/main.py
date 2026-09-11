from fastapi import FastAPI

from app.routes.upload import router as upload_router
from app.routes.scan import router as scan_router

from app.database.connection import Base, engine
from app.database import models


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SIH26034 Legal Metrology Compliance API",
    description="Backend API for packaged commodity label compliance checking.",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "SIH26034 Backend is running"
    }


app.include_router(upload_router)
app.include_router(scan_router)