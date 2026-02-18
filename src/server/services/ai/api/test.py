import logging

from fastapi import APIRouter

logger = logging.getLogger("ledgerai.test")

router = APIRouter()


@router.get("/test/weather")
async def get_weather():
    logger.info("Weather test endpoint called")
    return [
        {"date": "2026-02-17", "temperatureC": 5, "summary": "Chilly"},
        {"date": "2026-02-18", "temperatureC": 15, "summary": "Cool"},
        {"date": "2026-02-19", "temperatureC": 25, "summary": "Warm"},
        {"date": "2026-02-20", "temperatureC": -3, "summary": "Freezing"},
        {"date": "2026-02-21", "temperatureC": 35, "summary": "Hot"},
    ]
