from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.events import router as events_router
from app.config import get_settings
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    logger.info("Starting Bangkok Event Discovery API...")

    # Start background scraper if enabled
    if os.getenv("ENABLE_SCRAPER", "false").lower() == "true":
        try:
            from app.services.scraper import scraper_service
            await scraper_service.start()
            logger.info("Scraper service started")
        except Exception as e:
            logger.error(f"Failed to start scraper service: {e}")

    yield

    # Cleanup
    if os.getenv("ENABLE_SCRAPER", "false").lower() == "true":
        try:
            from app.services.scraper import scraper_service
            await scraper_service.stop()
        except Exception:
            pass

    logger.info("Shutting down...")


app = FastAPI(
    title="Bangkok Event Discovery API",
    description="API for discovering small-medium events in Bangkok",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(events_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {
        "message": "Bangkok Event Discovery API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/scraper/status")
async def scraper_status():
    """Get scraper service status"""
    try:
        from app.services.scraper import scraper_service
        return scraper_service.get_status()
    except Exception as e:
        return {"error": str(e), "is_running": False}


@app.post("/api/scraper/run")
async def trigger_scrape():
    """Manually trigger a scrape run"""
    try:
        from app.services.scraper import scraper_service
        import asyncio
        asyncio.create_task(scraper_service.run_web_scraper())
        return {"message": "Scrape triggered", "status": "running"}
    except Exception as e:
        return {"error": str(e)}
