import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CurrencyPipe } from '@angular/common';

interface Transaction {
  date: string;
  description: string;
  amount: number;
}

interface Category {
  name: string;
  type: 'income' | 'expense';
  transactions: Transaction[];
  total: number;
}

interface AnalysisResult {
  categories: Category[];
  total_income: number;
  total_expenses: number;
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

  constructor(private http: HttpClient) {}

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

  reset() {
    this.selectedFile.set(null);
    this.result.set(null);
    this.error.set(null);
  }
}
