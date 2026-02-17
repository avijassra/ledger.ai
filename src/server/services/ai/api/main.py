from fastapi import FastAPI
from test import router as test_router

app = FastAPI(title="LedgerAI Service", version="0.1.0")

app.include_router(test_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
