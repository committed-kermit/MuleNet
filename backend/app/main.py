from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ML artifacts, database session, memory graph
    print("🚀 Initializing MuleNet Risk Engine & Loading ML Artifacts...")
    yield
    # Shutdown: Clean up resources
    print("🛑 Shutting down MuleNet Risk Engine...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS middleware for React Vite Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "healthy", "service": settings.PROJECT_NAME}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
