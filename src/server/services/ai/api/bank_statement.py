import csv
import io
import json
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from providers.factory import get_ai_provider

logger = logging.getLogger("ledgerai.bank_statement")
router = APIRouter(prefix="/bank-statement")
_executor = ThreadPoolExecutor(max_workers=4)

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
    notes: str


class AnalysisResult(BaseModel):
    categories: list[Category]
    total_income: float
    total_expenses: float
    tax_deductible_expenses: list[TaxDeductibleCategory]
    total_tax_deductible: float


# ── CSV parsing ──────────────────────────────────────────────────────────────

_DATE_KEYS   = ['date', 'trans. date', 'transaction date', 'posted date', 'post date', 'trans date']
_DESC_KEYS   = ['description', 'merchant', 'memo', 'payee', 'name', 'narrative', 'details', 'particulars', 'transaction description']
_AMT_KEYS    = ['amount', 'transaction amount', 'net amount', 'amt']
_DEBIT_KEYS  = ['debit', 'withdrawal', 'charge', 'withdrawals', 'debit amount', 'debit amt']
_CREDIT_KEYS = ['credit', 'deposit', 'deposits', 'credit amount', 'credit amt', 'payment']


def _match_col(fieldnames: list[str], keywords: list[str]) -> str | None:
    for orig in fieldnames:
        lower = orig.strip().lower()
        if lower in keywords or any(k in lower for k in keywords):
            return orig
    return None


def _parse_amount(raw: str) -> float | None:
    raw = raw.strip().replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    if not raw or raw == '-':
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_csv_to_transactions(content: str, filename: str) -> list[dict]:
    """Parse a bank/credit-card CSV and return normalized transactions."""
    content = content.lstrip('\ufeff')  # strip BOM
    try:
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return []

        fnames = list(reader.fieldnames)
        date_col   = _match_col(fnames, _DATE_KEYS)
        desc_col   = _match_col(fnames, _DESC_KEYS)
        amt_col    = _match_col(fnames, _AMT_KEYS)
        debit_col  = _match_col(fnames, _DEBIT_KEYS)
        credit_col = _match_col(fnames, _CREDIT_KEYS)

        if not date_col or not desc_col:
            logger.warning("Could not detect date/description columns in '%s' — headers: %s", filename, fnames)
            return []

        transactions = []
        for row in reader:
            date = (row.get(date_col) or '').strip()
            desc = (row.get(desc_col) or '').strip()
            if not date or not desc:
                continue

            amount: float | None = None
            if amt_col:
                amount = _parse_amount(row.get(amt_col) or '')
            if amount is None and (debit_col or credit_col):
                debit  = _parse_amount(row.get(debit_col  or '', '') or '') or 0.0
                credit = _parse_amount(row.get(credit_col or '', '') or '') or 0.0
                if debit or credit:
                    # positive = income/credit-in, negative = expense/debit-out
                    amount = credit - debit
            if amount is None:
                continue

            transactions.append({
                'date': date,
                'description': desc.replace(',', ' '),
                'amount': round(amount, 2),
                'source': filename,
            })

        logger.info("Parsed %d transactions from '%s'", len(transactions), filename)
        return transactions

    except Exception as e:
        logger.warning("CSV parse error for '%s': %s", filename, e)
        return []


def _format_transactions(transactions: list[dict]) -> str:
    lines = ['Date,Description,Amount,Source']
    for t in transactions:
        lines.append(f"{t['date']},{t['description']},{t['amount']},{t['source']}")
    return '\n'.join(lines)


# ── Prompt ───────────────────────────────────────────────────────────────────

PROMPT = """Analyze the transaction data below. It may come from multiple bank accounts and credit cards.

IMPORTANT:
- Process EVERY SINGLE transaction — do not skip or sample any.
- Data may span an entire year across multiple files/accounts; include all months.
- All amounts use the sign convention: positive = income/credit, negative = expense/debit.

Return ONLY a raw JSON object (no markdown, no code fences) with this exact structure:
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
      "notes": "Brief explanation of eligibility and deduction percentage"
    }
  ],
  "total_tax_deductible": 0.0
}

Rules for categories:
- All amounts in the output must be POSITIVE numbers regardless of input sign.
- Use "type": "income" for money received (salary, deposits, refunds, transfers in).
- Use "type": "expense" for money spent (purchases, bills, fees, payments out).
- Group similar transactions into meaningful categories (Groceries, Dining, Utilities, Rent, Salary, Transportation, etc.).
- monthly_totals: one entry per calendar month with transactions, using "YYYY-MM" format.
- yearly_total = sum of all monthly_totals for that category.
- total_income = sum of yearly_total across all income categories.
- total_expenses = sum of yearly_total across all expense categories.

Rules for tax_deductible_expenses — map eligible transactions to THESE SPECIFIC CATEGORIES ONLY:
- "Commute": Gas stations, tolls, parking, Uber/Lyft/transit for work travel.
- "Medical": Doctor, dentist, hospital, pharmacy, health insurance premiums, FSA/HSA purchases.
- "Perdiem": Daily meal/incidental allowances when traveling overnight for business.
- "Team building event": Team dinners, group activities, office parties, employee outings.
- "Car Maintenance": Auto repair, oil changes, tires, car insurance, vehicle registration.
- "Education & Training": Books, online courses, certifications, professional conferences.
- "Business meeting": Client meals, coffee meetings (typically 50% deductible).
- "Donation": Charitable contributions to 501(c)(3) organizations, church, non-profits.
- "Internet": ISP bills (Comcast, Verizon Fios, Cox, etc.) for business use.
- "Phone Bills": Cell/mobile bills (AT&T, Verizon, T-Mobile, etc.).
- "Gym": Gym memberships, fitness clubs, yoga studios.
- "VA529": Virginia 529 college savings plan contributions.
- "Properties Maintenance": Repairs/maintenance for rental/investment properties.
- "HOA for Properties": HOA fees for rental/investment properties.
- "Corp Ins": Business liability, E&O, commercial auto, workers compensation insurance.
- "Software & Subscriptions": SaaS tools, QuickBooks, Microsoft 365, Adobe, project management apps.
- "Office Supplies": Paper, printer ink, stationery, shipping (FedEx, UPS), small office items.
- "Advertising & Marketing": Google/Meta Ads, website hosting, domain, business cards.
- "Professional Services": CPA, attorney, business consultant, bookkeeping fees.
- "Bank & Financial Fees": Business bank fees, wire transfer fees, credit card processing fees.
- "Office Rent": Co-working space, dedicated office or studio rent.
- "Business Travel": Flights, hotels, Airbnb for overnight business trips.
- "Home Office": Proportional rent/mortgage and utilities for a dedicated home workspace.
- "Mortgage Interest on Properties": Interest on rental/investment property mortgages.
- "Property Taxes": Real estate taxes on rental or investment properties.
- "Rental Property Utilities": Electricity, gas, water paid for rental properties.
- "Retirement Contributions": SEP-IRA, Solo 401(k), SIMPLE IRA (fully deductible for self-employed).
- "Electronics & Equipment": Computers, monitors, printers, cameras for business use (Section 179).
- "Student Loan Interest": Student loan interest (deductible up to $2,500/year).
- "Childcare & Dependent Care": FSA-eligible dependent care, daycare, after-school programs.

Only include a tax category if matching transactions exist. Set claimable_amount to the deductible portion (e.g. 50% for business meals). Omit categories with no matching transactions.
total_tax_deductible = sum of all claimable_amount values.
"""


# ── Endpoint ─────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/analyze")
async def analyze_statement(files: list[UploadFile] = File(...)):
    async def generate():
        try:
            yield _sse({"status": "parsing", "message": f"Reading {len(files)} file(s)..."})

            all_transactions: list[dict] = []
            raw_fallback_sections: list[str] = []
            pdf_bytes: bytes | None = None

            for f in files:
                filename = f.filename or "upload"
                mime = f.content_type or ""
                is_csv = filename.lower().endswith(".csv") or mime in ("text/csv", "application/csv", "application/vnd.ms-excel")
                is_pdf = filename.lower().endswith(".pdf") or mime == "application/pdf"

                raw = await f.read()

                if is_pdf:
                    if pdf_bytes is None:
                        pdf_bytes = raw
                    yield _sse({"status": "parsing", "message": f"Read PDF: {filename}"})
                else:
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("latin-1")

                    txns = parse_csv_to_transactions(text, filename)
                    if txns:
                        all_transactions.extend(txns)
                        yield _sse({"status": "parsing", "message": f"Parsed {len(txns):,} transactions from {filename}"})
                    else:
                        raw_fallback_sections.append(f"=== {filename} ===\n{text}")
                        yield _sse({"status": "parsing", "message": f"Read raw content from {filename}"})

            if not all_transactions and not raw_fallback_sections and pdf_bytes is None:
                yield _sse({"status": "error", "message": "No valid files could be parsed."})
                return

            # Build prompt
            total_txns = len(all_transactions)
            if all_transactions:
                txn_text = _format_transactions(all_transactions)
                full_prompt = f"Here are {total_txns:,} transactions from {len(files)} file(s):\n\n{txn_text}\n\n{PROMPT}"
                yield _sse({"status": "preparing", "message": f"Prepared {total_txns:,} transactions from {len(files)} file(s). Starting AI analysis..."})
            else:
                combined = "\n\n".join(raw_fallback_sections)
                full_prompt = f"Here is the transaction data from {len(files)} file(s):\n\n{combined}\n\n{PROMPT}"
                yield _sse({"status": "preparing", "message": f"Prepared data from {len(files)} file(s). Starting AI analysis..."})

            if pdf_bytes is not None and all_transactions:
                full_prompt = f"Additional PDF statement provided alongside the CSV data.\n\n{full_prompt}"

            # AI analysis
            yield _sse({"status": "analyzing", "message": "AI is analyzing all transactions. This may take a minute..."})

            try:
                provider = get_ai_provider()
            except (EnvironmentError, ValueError) as e:
                yield _sse({"status": "error", "message": str(e)})
                return

            start = time.time()
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(
                _executor, provider.analyze_bank_statement, full_prompt, pdf_bytes
            )
            duration = time.time() - start
            logger.info("%s completed in %.1fs", type(provider).__name__, duration)

            # Parse result
            yield _sse({"status": "processing", "message": f"AI analysis done ({duration:.0f}s). Parsing results..."})

            try:
                text = raw_response.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(text)
                result = AnalysisResult(**data)
                logger.info("Result: %d categories, income=%.2f, expenses=%.2f, tax=%.2f",
                            len(result.categories), result.total_income, result.total_expenses, result.total_tax_deductible)
                yield _sse({"status": "complete", "message": "Analysis complete!", "result": result.model_dump()})
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error("Failed to parse AI response: %s", e, exc_info=True)
                yield _sse({"status": "error", "message": f"Failed to parse AI response: {e}"})

        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            yield _sse({"status": "error", "message": f"Unexpected error: {e}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
