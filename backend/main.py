"""
Thai ALPR System - Main FastAPI Application
Enterprise-grade backend with async processing
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging
from pathlib import Path

# Import routers
from api.routes import (
    upload,
    verification,
    streaming,
    master_data,
    analytics,
    auth,
    export,
    websocket
)

# Import database
from database.connection import init_database, check_database_connection

# Import background tasks manager
from services.streaming_manager import StreamingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== LIFESPAN EVENTS ====================

streaming_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Thai ALPR System...")
    
    # Initialize database
    try:
        if check_database_connection():
            init_database()
            logger.info("✅ Database initialized")
        else:
            logger.error("❌ Database connection failed")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
    
    # Create necessary directories
    directories = [
        "storage/uploads",
        "storage/cropped_plates",
        "storage/original_images",
        "models"
    ]
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    logger.info("✅ Storage directories created")
    
    # Initialize streaming manager
    global streaming_manager
    streaming_manager = StreamingManager()
    logger.info("✅ Streaming manager initialized")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Thai ALPR System...")
    if streaming_manager:
        await streaming_manager.stop_all_streams()
    logger.info("✅ Graceful shutdown complete")


# ==================== CREATE FASTAPI APP ====================

app = FastAPI(
    title="Thai ALPR System",
    description="Enterprise Automatic License Plate Recognition System for Thai License Plates",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# ==================== MIDDLEWARE ====================

# CORS - Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Vue dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📥 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"📤 {request.method} {request.url.path} - Status: {response.status_code}")
    return response

# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if app.debug else "An error occurred"
        }
    )

# ==================== ROUTES ====================

# Health check
@app.get("/health")
async def health_check():
    """System health check"""
    db_status = check_database_connection()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "version": "1.0.0"
    }

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload & Processing"])
app.include_router(verification.router, prefix="/api/verification", tags=["Verification"])
app.include_router(streaming.router, prefix="/api/streaming", tags=["Video Streaming"])
app.include_router(master_data.router, prefix="/api/master-data", tags=["Master Data"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(export.router, prefix="/api/export", tags=["Export Reports"])
app.include_router(websocket.router, prefix="/api", tags=["WebSocket Notifications"])

# Serve static files (uploaded images, cropped plates)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# ==================== ROOT ENDPOINT ====================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Thai ALPR System API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }

# ==================== MAIN ====================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Set False in production
        log_level="info",
        access_log=True
    )
