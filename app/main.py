"""
Application entry point.

This is the file uvicorn loads. The `app` object here is what uvicorn serves.

Python concept: "app factory" pattern. We create the FastAPI instance,
configure it, and register all routers here. This keeps the file as a
single "wiring" point — easy to see what's connected to what.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Python concept: An "async context manager" (like Java's try-with-resources).
    Code before `yield` runs at startup. Code after runs at shutdown.
    FastAPI calls this once when the server starts/stops.
    """
    # Ensure data directory exists (SQLite needs it)
    Path("data").mkdir(exist_ok=True)
    Path(settings.backup_dir).mkdir(exist_ok=True)
    yield
    # Shutdown cleanup (if needed)


app = FastAPI(
    title=settings.app_name,
    description=f"{settings.app_tagline} — Order Management System",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 templates (HTML pages)
templates = Jinja2Templates(directory="app/templates")

# Make settings available to all routes via app.state
app.state.settings = settings
app.state.templates = templates

@app.get("/health")
async def health():
    """Health check endpoint. Returns 200 if the app is alive."""
    return {"status": "ok", "app": settings.app_name}

@app.get("/favicon.ico")
async def favicon():
    """Returns a small SVG cupcake as the favicon. Eliminates the 404."""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <text y=".9em" font-size="90">🧁</text>
    </svg>'''
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")


# Register routers
from app.routers import dashboard, products, customers, orders, invoices, export, audit, settings as settings_router
app.include_router(dashboard.router)
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(customers.router, prefix="/customers", tags=["Customers"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
app.include_router(export.router, tags=["Export"])
app.include_router(audit.router, tags=["Audit"])
app.include_router(settings_router.router, tags=["Settings"])


# Allow running directly: python -m app.main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)   