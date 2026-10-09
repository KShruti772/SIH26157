import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, init_db
from app.routers import api

# Create and migrate tables
init_db()

app = FastAPI(
    title="SAT-SA",
    description="Supervisory Analytics Tool for SOC Assessment (SIH26157)",
    version="1.0.0",
)

# Configurable explicit CORS origins suitable for local/offline deployment
cors_origins_raw = os.environ.get(
    "SAT_SA_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080"
)
allowed_origins = [orig.strip() for orig in cors_origins_raw.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount public and protected API routers
app.include_router(api.public_router, prefix="/api")
app.include_router(api.protected_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to SAT-SA API"}
