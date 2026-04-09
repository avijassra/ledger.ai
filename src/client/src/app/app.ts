import { Component, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

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
  imports: [CurrencyPipe, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly selectedFiles = signal<File[]>([]);
  protected readonly loading = signal(false);
  protected readonly result = signal<AnalysisResult | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly dragging = signal(false);

  // Custom categories added by user
  protected readonly customCategories = signal<TaxDeductibleCategory[]>([]);
  protected readonly showAddCategory = signal(false);
  protected newCategoryName = '';
  protected newCategoryAmount: number | null = null;
  protected newCategoryNotes = '';

  protected readonly allMonths = computed(() => {
    const result = this.result();
    if (!result) return [];
    const months = new Set<string>();
    for (const cat of result.categories) {
      for (const m of cat.monthly_totals) months.add(m.month);
    }
    return Array.from(months).sort();
  });

  protected readonly allTaxCategories = computed(() => {
    const result = this.result();
    if (!result) return this.customCategories();
    return [...result.tax_deductible_expenses, ...this.customCategories()];
  });

  protected readonly totalTaxDeductible = computed(() => {
    return this.allTaxCategories().reduce((sum, c) => sum + c.claimable_amount, 0);
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
      this.addFiles(Array.from(input.files));
      input.value = '';
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
    if (event.dataTransfer?.files.length) {
      this.addFiles(Array.from(event.dataTransfer.files));
    }
  }

  private addFiles(incoming: File[]) {
    const valid: File[] = [];
    const errors: string[] = [];

    for (const file of incoming) {
      const isCsv = file.type === 'text/csv' || file.type === 'application/csv' || file.name.toLowerCase().endsWith('.csv');
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      if (!isCsv && !isPdf) {
        errors.push(`"${file.name}" is not a CSV or PDF file`);
      } else {
        valid.push(file);
      }
    }

    if (errors.length) {
      this.error.set(errors.join('; '));
    } else {
      this.error.set(null);
    }

    if (valid.length) {
      const existing = this.selectedFiles();
      const names = new Set(existing.map(f => f.name));
      const deduped = valid.filter(f => !names.has(f.name));
      this.selectedFiles.set([...existing, ...deduped]);
      this.result.set(null);
    }
  }

  removeFile(index: number) {
    const files = [...this.selectedFiles()];
    files.splice(index, 1);
    this.selectedFiles.set(files);
  }

  analyze() {
    const files = this.selectedFiles();
    if (!files.length) return;

    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    this.loading.set(true);
    this.error.set(null);
    this.result.set(null);
    this.customCategories.set([]);

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

  addCategory() {
    const name = this.newCategoryName.trim();
    const amount = this.newCategoryAmount ?? 0;
    if (!name || amount <= 0) return;

    this.customCategories.update(cats => [
      ...cats,
      { name, claimable_amount: amount, notes: this.newCategoryNotes.trim() || 'Manually added' }
    ]);

    this.newCategoryName = '';
    this.newCategoryAmount = null;
    this.newCategoryNotes = '';
    this.showAddCategory.set(false);
  }

  removeCustomCategory(index: number) {
    this.customCategories.update(cats => {
      const copy = [...cats];
      copy.splice(index, 1);
      return copy;
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
    rows.push(`Total Tax Deductible,${this.totalTaxDeductible().toFixed(2)}`);
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

    // Section 4: Tax deductible expenses (AI + custom)
    rows.push('TAX DEDUCTIBLE EXPENSES');
    rows.push([q('Category'), q('Claimable Amount'), q('Notes')].join(','));
    for (const t of this.allTaxCategories()) {
      rows.push([q(t.name), q(t.claimable_amount.toFixed(2)), q(t.notes)].join(','));
    }
    rows.push([q('Total Tax Deductible'), q(this.totalTaxDeductible().toFixed(2)), q('')].join(','));

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'expense_analysis.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  reset() {
    this.selectedFiles.set([]);
    this.result.set(null);
    this.error.set(null);
    this.customCategories.set([]);
  }
}
