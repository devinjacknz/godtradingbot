from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.auth.router import router as auth_router

app = FastAPI(title="Trading Bot API Gateway")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/")
async def root():
    return {"message": "Trading Bot API Gateway"}
