from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, goals, insights, settings as settings_routes, transactions, weeks
from app.core.config import settings
from app.core.log_config import RequestIdMiddleware, setup_logging

setup_logging()

app = FastAPI(title="FinFlow API", version="1.0.0", redirect_slashes=False)

# RequestIdMiddleware must be added first (outermost layer) so trace_id is set
# before any other middleware or route handler emits log lines.
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(weeks.router, prefix="/api/v1/weeks", tags=["weeks"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])
app.include_router(goals.router, prefix="/api/v1/goals", tags=["goals"])
app.include_router(settings_routes.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None  # not running in Lambda context
