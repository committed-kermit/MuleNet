from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.core.db import init_db
from app.api.routes_scoring import router as scoring_router
from app.api.routes_cases import router as cases_router
from app.api.routes_graph import router as graph_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_demo import router as demo_router
from app.api.routes_simulator import router as simulator_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB schema
    print("[MuleNet] Initializing DB schema and loading forensic models...")
    init_db()
    yield
    # Shutdown
    print("[MuleNet] Shutting down AML risk engine...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(scoring_router, prefix=settings.API_V1_STR)
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(graph_router, prefix=settings.API_V1_STR)
app.include_router(metrics_router, prefix=settings.API_V1_STR)
app.include_router(demo_router, prefix=settings.API_V1_STR)
app.include_router(simulator_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
