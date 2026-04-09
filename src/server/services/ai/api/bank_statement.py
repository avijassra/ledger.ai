import json
import logging
import time

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from providers.factory import get_ai_provider

logger = logging.getLogger("ledgerai.bank_statement")

router = APIRouter(prefix="/bank-statement")

ACCEPTED_MIME_TYPES = {
    "application/pdf",
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


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


PROMPT = """Analyze the provided bank statement data (CSV files and/or PDF). Extract all transactions, categorize them, and produce a full tax-deductible expense analysis.

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
      "notes": "Brief explanation of eligibility and applicable deduction percentage"
    }
  ],
  "total_tax_deductible": 0.0
}

Rules for categories:
- All amounts should be positive numbers
- Use "type": "income" for money received (salary, refunds, transfers in, deposits, etc.)
- Use "type": "expense" for money spent (purchases, bills, fees, etc.)
- Group similar transactions into meaningful categories (e.g., Groceries, Dining, Utilities, Rent, Salary, Transportation, Entertainment, etc.)
- monthly_totals must include one entry per calendar month that has transactions, using "YYYY-MM" format
- yearly_total is the sum of all monthly_totals for that category
- total_income is the sum of yearly_total across all income categories
- total_expenses is the sum of yearly_total across all expense categories

Rules for tax_deductible_expenses — map eligible transactions to THESE SPECIFIC CATEGORIES ONLY:
- "Commute": Gas stations, tolls, parking, Uber/Lyft/transit used for work travel (IRS standard mileage or actual expenses)
- "Medical": Doctor, dentist, hospital, pharmacy, health insurance premiums, FSA/HSA-eligible purchases
- "Perdiem": Daily meal/incidental allowances when traveling overnight for business (IRS per diem rates apply)
- "Team building event": Team dinners, group activities, office parties, employee outings
- "Car Maintenance": Auto repair shops, oil changes, tires, car insurance, vehicle registration for business use
- "Education & Training": Books, online courses (Udemy, Coursera, LinkedIn Learning), certifications, professional conferences
- "Business meeting": Client meals, coffee meetings with clients/prospects (typically 50% deductible)
- "Donation": Charitable contributions to 501(c)(3) organizations, church, non-profits
- "Internet": ISP bills (Comcast, Verizon Fios, Cox, etc.), internet service for business use
- "Phone Bills": Cell phone/mobile bills (AT&T, Verizon, T-Mobile, etc.), business phone expenses
- "Gym": Gym memberships, fitness clubs, yoga studios (if health-related business deduction applies)
- "VA529": Virginia 529 college savings plan contributions (Virginia state tax deduction)
- "Properties Maintenance": Repairs, maintenance, supplies for rental/investment properties (Home Depot, Lowe's, contractors)
- "HOA for Properties": Homeowners association fees for rental/investment properties
- "Corp Ins": Business liability insurance, E&O insurance, commercial auto, workers compensation premiums
- "Software & Subscriptions": SaaS tools, QuickBooks, Microsoft 365, Adobe Creative Cloud, project management apps, business software
- "Office Supplies": Paper, printer ink, stationery, shipping/postage (FedEx, UPS), small office items
- "Advertising & Marketing": Google Ads, Facebook/Meta Ads, website hosting, domain registration, business cards, marketing services
- "Professional Services": CPA/accountant fees, attorney fees, business consultant fees, bookkeeping services
- "Bank & Financial Fees": Business bank fees, wire transfer fees, credit card processing fees, merchant service fees
- "Office Rent": Co-working space (WeWork, Regus), dedicated office or studio rent payments
- "Business Travel": Flights, hotels, Airbnb for overnight business trips (distinct from local commute)
- "Home Office": Proportional share of rent/mortgage interest and utilities for a dedicated home workspace
- "Mortgage Interest on Properties": Interest portion of mortgage payments for rental/investment properties
- "Property Taxes": Real estate/property taxes paid on rental or investment properties
- "Rental Property Utilities": Electricity, gas, water paid on behalf of rental properties
- "Retirement Contributions": SEP-IRA, Solo 401(k), SIMPLE IRA contributions (fully deductible for self-employed)
- "Electronics & Equipment": Computers, monitors, printers, cameras, and other equipment purchased for business use (Section 179)
- "Student Loan Interest": Student loan interest payments (deductible up to $2,500/year)
- "Childcare & Dependent Care": FSA-eligible dependent care expenses, daycare, after-school programs

Only include a tax category if relevant transactions exist. Set claimable_amount to the deductible portion (e.g., 50% for business meals, 100% for retirement contributions). If no transactions match a category, omit it entirely.
total_tax_deductible is the sum of all claimable_amount values.
"""


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_statement(files: list[UploadFile] = File(...)):
    logger.info("Received analysis request: %d file(s)", len(files))

    csv_sections: list[str] = []
    pdf_bytes: bytes | None = None

    for f in files:
        filename = f.filename or ""
        mime = f.content_type or ""
        is_csv = filename.lower().endswith(".csv") or mime in ("text/csv", "application/csv", "application/vnd.ms-excel")
        is_pdf = filename.lower().endswith(".pdf") or mime == "application/pdf"

        if not is_csv and not is_pdf and mime not in ACCEPTED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for '{filename}': {mime}")

        raw = await f.read()
        logger.info("Read file '%s': %d bytes, content_type=%s", filename, len(raw), mime)

        if is_pdf and pdf_bytes is None:
            pdf_bytes = raw
        elif is_csv or (mime in ("text/plain", "application/octet-stream") and not is_pdf):
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            csv_sections.append(f"=== {filename} ===\n{text}")

    if not csv_sections and pdf_bytes is None:
        raise HTTPException(status_code=400, detail="No valid CSV or PDF files uploaded")

    full_prompt = PROMPT
    if csv_sections:
        combined_csv = "\n\n".join(csv_sections)
        full_prompt = f"Here is the transaction data from the uploaded file(s):\n\n{combined_csv}\n\n{PROMPT}"

    try:
        provider = get_ai_provider()
    except (EnvironmentError, ValueError) as e:
        logger.error("AI provider configuration error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Sending to %s for analysis (pdf=%s, csv_files=%d)", type(provider).__name__, pdf_bytes is not None, len(csv_sections))
    start = time.time()
    raw_response = provider.analyze_bank_statement(full_prompt, pdf_bytes)
    duration = time.time() - start
    logger.info("%s response received in %.2fs", type(provider).__name__, duration)

    try:
        text = raw_response.strip()
        if text.startswith("```"):
            logger.info("Stripping markdown code fences from AI response")
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        result = AnalysisResult(**data)
        logger.info("Parsed result: %d categories, income=%.2f, expenses=%.2f, tax_deductible=%.2f",
                    len(result.categories), result.total_income, result.total_expenses, result.total_tax_deductible)
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse AI response: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {e}")
