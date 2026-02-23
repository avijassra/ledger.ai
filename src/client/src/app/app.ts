import { Component, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CurrencyPipe } from '@angular/common';

interface Transaction {
  date: string;
  description: string;
  amount: number;
}

interface MonthlyAmount {
  month: string;
  amount: number;
}

interface Category {
  name: string;
  type: 'income' | 'expense';
  transactions: Transaction[];
  monthly_totals: MonthlyAmount[];
  yearly_total: number;
}

interface TaxDeductibleCategory {
  name: string;
  claimable_amount: number;
  notes: string;
}

interface AnalysisResult {
  categories: Category[];
  total_income: number;
  total_expenses: number;
  tax_deductible_expenses: TaxDeductibleCategory[];
  total_tax_deductible: number;
}

@Component({
  selector: 'app-root',
  imports: [CurrencyPipe],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly selectedFile = signal<File | null>(null);
  protected readonly loading = signal(false);
  protected readonly result = signal<AnalysisResult | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly dragging = signal(false);

  protected readonly allMonths = computed(() => {
    const result = this.result();
    if (!result) return [];
    const months = new Set<string>();
    for (const cat of result.categories) {
      for (const m of cat.monthly_totals) months.add(m.month);
    }
    return Array.from(months).sort();
  });

  constructor(private http: HttpClient) {}

  protected getMonthlyAmount(category: Category, month: string): number {
    return category.monthly_totals.find(m => m.month === month)?.amount ?? 0;
  }

  protected formatMonth(month: string): string {
    const [year, mon] = month.split('-');
    return new Date(+year, +mon - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.setFile(input.files[0]);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files[0];
    if (file) {
      this.setFile(file);
    }
  }

  private setFile(file: File) {
    if (file.type !== 'application/pdf') {
      this.error.set('Please select a PDF file');
      return;
    }
    this.selectedFile.set(file);
    this.error.set(null);
    this.result.set(null);
  }

  analyze() {
    const file = this.selectedFile();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    this.loading.set(true);
    this.error.set(null);
    this.result.set(null);

    this.http.post<AnalysisResult>('/BankStatement/analyze', formData).subscribe({
      next: (data) => {
        this.result.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to analyze statement. Please try again.');
        this.loading.set(false);
      }
    });
  }

  exportToCsv(): void {
    const result = this.result();
    if (!result) return;

    const months = this.allMonths();
    const rows: string[] = [];
    const q = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;

    // Section 1: Summary
    rows.push('SUMMARY');
    rows.push(`Total Income,${result.total_income.toFixed(2)}`);
    rows.push(`Total Expenses,${result.total_expenses.toFixed(2)}`);
    rows.push(`Net,${(result.total_income - result.total_expenses).toFixed(2)}`);
    rows.push(`Total Tax Deductible,${result.total_tax_deductible.toFixed(2)}`);
    rows.push('');

    // Section 2: Monthly category breakdown
    rows.push('MONTHLY CATEGORY BREAKDOWN');
    rows.push([q('Category'), q('Type'), ...months.map(m => q(this.formatMonth(m))), q('Yearly Total')].join(','));
    for (const cat of result.categories) {
      rows.push([
        q(cat.name),
        q(cat.type),
        ...months.map(m => q(this.getMonthlyAmount(cat, m).toFixed(2))),
        q(cat.yearly_total.toFixed(2)),
      ].join(','));
    }
    rows.push('');

    // Section 3: All transactions
    rows.push('ALL TRANSACTIONS');
    rows.push([q('Category'), q('Type'), q('Date'), q('Description'), q('Amount')].join(','));
    for (const cat of result.categories) {
      for (const tx of cat.transactions) {
        rows.push([q(cat.name), q(cat.type), q(tx.date), q(tx.description), q(tx.amount.toFixed(2))].join(','));
      }
    }
    rows.push('');

    // Section 4: Tax deductible expenses
    rows.push('TAX DEDUCTIBLE EXPENSES');
    rows.push([q('Category'), q('Claimable Amount'), q('Notes')].join(','));
    for (const t of result.tax_deductible_expenses) {
      rows.push([q(t.name), q(t.claimable_amount.toFixed(2)), q(t.notes)].join(','));
    }
    rows.push([q('Total Tax Deductible'), q(result.total_tax_deductible.toFixed(2)), q('')].join(','));

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bank_statement_analysis.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  reset() {
    this.selectedFile.set(null);
    this.result.set(null);
    this.error.set(null);
  }
}
