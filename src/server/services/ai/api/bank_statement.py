import json
import logging
import time

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from providers.factory import get_ai_provider

logger = logging.getLogger("ledgerai.bank_statement")

router = APIRouter(prefix="/bank-statement")


class Transaction(BaseModel):
    date: str
    description: str
    amount: float


class MonthlyAmount(BaseModel):
    month: str  # "YYYY-MM"
    amount: float


class Category(BaseModel):
    name: str
    type: str  # "income" or "expense"
    transactions: list[Transaction]
    monthly_totals: list[MonthlyAmount]
    yearly_total: float


class TaxDeductibleCategory(BaseModel):
    name: str
    claimable_amount: float
    notes: str  # explanation of eligibility


class AnalysisResult(BaseModel):
    categories: list[Category]
    total_income: float
    total_expenses: float
    tax_deductible_expenses: list[TaxDeductibleCategory]
    total_tax_deductible: float


PROMPT = """Analyze this bank statement PDF. Extract all transactions, categorize them, and produce a full yearly tax-deductible expense analysis.

Return a JSON object with this exact structure (no markdown, no code fences, just raw JSON):
{
  "categories": [
    {
      "name": "Category Name",
      "type": "income" or "expense",
      "transactions": [
        {"date": "YYYY-MM-DD", "description": "...", "amount": 123.45}
      ],
      "monthly_totals": [
        {"month": "YYYY-MM", "amount": 123.45}
      ],
      "yearly_total": 123.45
    }
  ],
  "total_income": 0.0,
  "total_expenses": 0.0,
  "tax_deductible_expenses": [
    {
      "name": "Category Name",
      "claimable_amount": 123.45,
      "notes": "Brief explanation of why and how this expense qualifies as a tax deduction"
    }
  ],
  "total_tax_deductible": 0.0
}

Rules:
- All amounts should be positive numbers
- Use "type": "income" for money received (salary, refunds, transfers in, etc.)
- Use "type": "expense" for money spent (purchases, bills, fees, etc.)
- Group similar transactions into meaningful categories (e.g., Groceries, Dining, Utilities, Rent, Salary, Transportation, Entertainment, Healthcare, Professional Services, etc.)
- monthly_totals must include one entry per calendar month that has transactions for that category, using "YYYY-MM" format
- yearly_total is the sum of all monthly_totals for that category
- total_income is the sum of yearly_total across all income categories
- total_expenses is the sum of yearly_total across all expense categories
- For tax_deductible_expenses, include only expense categories that are commonly eligible for income tax deductions (e.g., Home Office, Professional Development, Business Travel, Medical/Healthcare, Charitable Donations, Professional Services, Business Meals at 50%, etc.)
- claimable_amount reflects the deductible portion (e.g., 50% for business meals, 100% for home office supplies)
- notes should briefly explain the eligibility and any applicable percentage or limit
- total_tax_deductible is the sum of all claimable_amount values
"""


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_statement(file: UploadFile = File(...)):
    logger.info("Received bank statement analysis request: filename=%s, content_type=%s", file.filename, file.content_type)

    if file.content_type != "application/pdf":
        logger.warning("Rejected non-PDF file: content_type=%s", file.content_type)
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    logger.info("Read PDF file: size=%d bytes", len(pdf_bytes))

    try:
        provider = get_ai_provider()
    except (EnvironmentError, ValueError) as e:
        logger.error("AI provider configuration error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Sending PDF to %s for analysis", type(provider).__name__)
    start = time.time()
    raw = provider.analyze_bank_statement(pdf_bytes, PROMPT)
    duration = time.time() - start
    logger.info("%s response received in %.2fs", type(provider).__name__, duration)

    try:
        raw = raw.strip()
        if raw.startswith("```"):
            logger.info("Stripping markdown code fences from AI response")
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        result = AnalysisResult(**data)
        logger.info("Successfully parsed analysis result: %d categories, income=%.2f, expenses=%.2f, tax_deductible=%.2f",
                     len(result.categories), result.total_income, result.total_expenses, result.total_tax_deductible)
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse AI response: %s", e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to parse AI response: {e}",
        )
