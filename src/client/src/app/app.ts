import { Component, computed, signal } from '@angular/core';
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

type StatusPhase = 'idle' | 'uploading' | 'parsing' | 'preparing' | 'analyzing' | 'processing' | 'complete' | 'error';

const PHASE_STEP: Record<StatusPhase, number> = {
  idle: 0, uploading: 10, parsing: 25, preparing: 45, analyzing: 60, processing: 90, complete: 100, error: 0,
};

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

  // Status tracking
  protected readonly statusPhase = signal<StatusPhase>('idle');
  protected readonly statusMessage = signal('');
  protected readonly statusProgress = computed(() => PHASE_STEP[this.statusPhase()]);

  // Custom categories
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
    const base = result ? result.tax_deductible_expenses : [];
    return [...base, ...this.customCategories()];
  });

  protected readonly totalTaxDeductible = computed(() =>
    this.allTaxCategories().reduce((sum, c) => sum + c.claimable_amount, 0)
  );

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
        errors.push(`"${file.name}" is not a CSV or PDF`);
      } else {
        valid.push(file);
      }
    }
    if (errors.length) this.error.set(errors.join('; '));
    else this.error.set(null);

    if (valid.length) {
      const existing = this.selectedFiles();
      const names = new Set(existing.map(f => f.name));
      this.selectedFiles.set([...existing, ...valid.filter(f => !names.has(f.name))]);
      this.result.set(null);
    }
  }

  removeFile(index: number) {
    const files = [...this.selectedFiles()];
    files.splice(index, 1);
    this.selectedFiles.set(files);
  }

  async analyze() {
    const files = this.selectedFiles();
    if (!files.length) return;

    const formData = new FormData();
    for (const file of files) formData.append('files', file);

    this.loading.set(true);
    this.error.set(null);
    this.result.set(null);
    this.customCategories.set([]);
    this.statusPhase.set('uploading');
    this.statusMessage.set('Uploading files...');

    try {
      const response = await fetch('/BankStatement/analyze', { method: 'POST', body: formData });

      if (!response.ok || !response.body) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            const phase = data.status as StatusPhase;
            this.statusPhase.set(phase);
            this.statusMessage.set(data.message ?? '');

            if (phase === 'complete') {
              this.result.set(data.result);
              this.loading.set(false);
            } else if (phase === 'error') {
              this.error.set(data.message ?? 'An error occurred');
              this.loading.set(false);
            }
          } catch { /* ignore parse errors on individual SSE lines */ }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to analyze. Please try again.';
      this.error.set(msg);
      this.statusPhase.set('error');
      this.loading.set(false);
    }
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
    this.customCategories.update(cats => { const c = [...cats]; c.splice(index, 1); return c; });
  }

  exportToCsv(): void {
    const result = this.result();
    if (!result) return;
    const months = this.allMonths();
    const rows: string[] = [];
    const q = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;

    rows.push('SUMMARY');
    rows.push(`Total Income,${result.total_income.toFixed(2)}`);
    rows.push(`Total Expenses,${result.total_expenses.toFixed(2)}`);
    rows.push(`Net,${(result.total_income - result.total_expenses).toFixed(2)}`);
    rows.push(`Total Tax Deductible,${this.totalTaxDeductible().toFixed(2)}`);
    rows.push('');

    rows.push('MONTHLY CATEGORY BREAKDOWN');
    rows.push([q('Category'), q('Type'), ...months.map(m => q(this.formatMonth(m))), q('Yearly Total')].join(','));
    for (const cat of result.categories) {
      rows.push([q(cat.name), q(cat.type), ...months.map(m => q(this.getMonthlyAmount(cat, m).toFixed(2))), q(cat.yearly_total.toFixed(2))].join(','));
    }
    rows.push('');

    rows.push('ALL TRANSACTIONS');
    rows.push([q('Category'), q('Type'), q('Date'), q('Description'), q('Amount')].join(','));
    for (const cat of result.categories) {
      for (const tx of cat.transactions) {
        rows.push([q(cat.name), q(cat.type), q(tx.date), q(tx.description), q(tx.amount.toFixed(2))].join(','));
      }
    }
    rows.push('');

    rows.push('TAX DEDUCTIBLE EXPENSES');
    rows.push([q('Category'), q('Claimable Amount'), q('Notes')].join(','));
    for (const t of this.allTaxCategories()) {
      rows.push([q(t.name), q(t.claimable_amount.toFixed(2)), q(t.notes)].join(','));
    }
    rows.push([q('Total Tax Deductible'), q(this.totalTaxDeductible().toFixed(2)), q('')].join(','));

    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
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
    this.statusPhase.set('idle');
    this.statusMessage.set('');
  }
}
