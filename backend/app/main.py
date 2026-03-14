"""FastAPI Main Application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.db import mongodb, vector_db
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting Second Brain GraphRAG Backend...")
    
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    
    # Connect to MongoDB
    try:
        await mongodb.connect()
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise
    
    # Connect to MongoDB Atlas Vector Search
    try:
        await vector_db.connect(mongodb.db)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Vector Search: {e}")
        logger.warning("⚠️ Vector search will not be available")
    
    logger.info("✅ All databases connected successfully")
    logger.info(f"🌐 API running at http://{settings.api_host}:{settings.api_port}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    await mongodb.disconnect()
    await vector_db.disconnect()
    logger.info("✅ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Second Brain GraphRAG API",
    description="Graph Retrieval Augmented Generation Backend with Vector Database",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint - Second Brain API"""
    return {
        "message": "Second Brain GraphRAG API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mongodb": "connected" if mongodb.db is not None else "disconnected",
        "vector_db": "connected" if vector_db.client is not None else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
    )
