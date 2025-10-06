from fastapi import FastAPI
from .api import api_pdf

app = FastAPI(
    title="PDF Microservice",
    description="PDF compression and manipulation service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(prefix="/api/v1", router=api_pdf.router)
