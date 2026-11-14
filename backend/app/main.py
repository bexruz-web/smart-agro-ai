"""FastAPI ilovasi."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_farmer, routes_system
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(title="Smart Agro AI API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

origins = [o for o in [settings.webapp_url.rstrip("/") if settings.webapp_url else None] if o]
if settings.app_env == "development":
    origins += ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning"])


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


app.include_router(routes_system.router)
app.include_router(routes_system.internal)
app.include_router(routes_farmer.router)
