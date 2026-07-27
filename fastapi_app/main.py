import os
import sys

# Ensure parent directory is in sys.path so 'fastapi_app' and 'src' modules can be resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from fastapi_app.routers import auth, admin, client
from src.Models import database

# 1. Setup Loguru Logger
# Create a logs directory inside workspace if it doesn't exist
os.makedirs("logs", exist_ok=True)
logger.remove()  # Remove default logger to prevent duplicate logs
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/api.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    rotation="10 MB",
    retention="10 days",
)

logger.info("Initializing SQLite database...")
# 2. Initialize SQLite Database schemas on startup
try:
    database.init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Database initialization failure: {e}")

# 3. Create FastAPI application instance
app = FastAPI(
    title="Multi-Tenant IMAP Email Manager REST API",
    description="Exposes core email manager, authentication, and client administration workflows.",
    version="1.0.0"
)

# 4. Enable Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Add Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"Completed request: {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {process_time:.2f}ms"
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.exception(
            f"Failed request: {request.method} {request.url.path} | "
            f"Error: {str(e)} | "
            f"Duration: {process_time:.2f}ms"
        )
        raise e

# 6. Mount API Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(client.router)


@app.get("/")
def read_root():
    """
    Basic API root status information.
    """
    return {
        "status": "online",
        "api_name": "Multi-Tenant IMAP Email Manager REST API",
        "documentation": "/docs"
    }
