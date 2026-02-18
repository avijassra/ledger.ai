import json
import logging
import os
import time

from fastapi import APIRouter, UploadFile, File, HTTPException
from google import genai
from pydantic import BaseModel

logger = logging.getLogger("ledgerai.bank_statement")

router = APIRouter(prefix="/bank-statement")


class Transaction(BaseModel):
    date: str
    description: str
    amount: float


class Category(BaseModel):
    name: str
    type: str  # "income" or "expense"
    transactions: list[Transaction]
    total: float


class AnalysisResult(BaseModel):
    categories: list[Category]
    total_income: float
    total_expenses: float


PROMPT = """Analyze this bank statement PDF. Extract all transactions and categorize them.

Return a JSON object with this exact structure (no markdown, no code fences, just raw JSON):
{
  "categories": [
    {
      "name": "Category Name",
      "type": "income" or "expense",
      "transactions": [
        {"date": "YYYY-MM-DD", "description": "...", "amount": 123.45}
      ],
      "total": 123.45
    }
  ],
  "total_income": 0.0,
  "total_expenses": 0.0
}

Rules:
- All amounts should be positive numbers
- Use "type": "income" for money received (salary, refunds, transfers in, etc.)
- Use "type": "expense" for money spent (purchases, bills, fees, etc.)
- Group similar transactions into meaningful categories (e.g., Groceries, Dining, Utilities, Rent, Salary, Transportation, Entertainment, Healthcare, etc.)
- total_income is the sum of all income category totals
- total_expenses is the sum of all expense category totals
- Each category's total is the sum of its transaction amounts
"""


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_statement(file: UploadFile = File(...)):
    logger.info("Received bank statement analysis request: filename=%s, content_type=%s", file.filename, file.content_type)

    if file.content_type != "application/pdf":
        logger.warning("Rejected non-PDF file: content_type=%s", file.content_type)
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    logger.info("Read PDF file: size=%d bytes", len(pdf_bytes))

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not configured")
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    client = genai.Client(api_key=api_key)

    logger.info("Sending PDF to Gemini API for analysis")
    start = time.time()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PROMPT,
        ],
    )
    duration = time.time() - start
    logger.info("Gemini API response received in %.2fs", duration)

    try:
        raw = response.text.strip()
        if raw.startswith("```"):
            logger.info("Stripping markdown code fences from AI response")
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        result = AnalysisResult(**data)
        logger.info("Successfully parsed analysis result: %d categories, income=%.2f, expenses=%.2f",
                     len(result.categories), result.total_income, result.total_expenses)
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse AI response: %s", e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to parse AI response: {e}",
        )
