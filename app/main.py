import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import certificates, health, jobs, verify
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.base import Base, engine
from app.workers.processor import recover_stuck_jobs_on_startup

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for database initialization and crash recovery."""
    logger.info("Initializing Database Tables...")
    Base.metadata.create_all(bind=engine)

    logger.info("Running stuck job crash recovery handler...")
    try:
        recover_stuck_jobs_on_startup()
    except Exception as e:
        logger.error(f"Error recovering stuck jobs: {e}")

    yield

    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.APP_TITLE,
    version="1.0.0",
    description="Bulk Certificate Generator API with fault-tolerant background worker and PDF template renderer.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers with /api prefix
app.include_router(jobs.router, prefix="/api")
app.include_router(certificates.router, prefix="/api")
app.include_router(verify.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# Static files mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def read_root():
    """Serve the Web UI homepage."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Bulk Certificate Generator API. Visit /docs for API documentation."}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global unhandled exception handler to ensure standard error response format."""
    logger.exception(f"Unhandled Server Error on {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred while processing your request."
            }
        }
    )
