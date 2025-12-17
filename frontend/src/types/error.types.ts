import { ReactNode } from 'react';

export class ErrorBoundary extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ErrorBoundary';
  }
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}
