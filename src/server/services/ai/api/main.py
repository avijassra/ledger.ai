import logging

from fastapi import FastAPI
from dotenv import load_dotenv
from test import router as test_router
from bank_statement import router as bank_statement_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ledgerai")

app = FastAPI(title="LedgerAI Service", version="0.1.0")

app.include_router(test_router)
app.include_router(bank_statement_router)


@app.on_event("startup")
async def startup_event():
    logger.info("LedgerAI AI service starting up")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("LedgerAI AI service shutting down")


@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}
