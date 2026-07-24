import { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Card } from './common';

interface Props {
  children: ReactNode;
  title?: string;
  onRetry?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: unknown): void {
    console.error('[ErrorBoundary]', this.props.title || 'section', error, errorInfo);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
    if (this.props.onRetry) this.props.onRetry();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Card>
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <AlertTriangle className="h-7 w-7 text-amber-400" />
            <div className="text-sm font-medium text-white">
              {this.props.title || 'Algo salio mal'}
            </div>
            <div className="text-xs text-tnvs-muted max-w-md">
              {this.state.error?.message || 'Error desconocido'}
            </div>
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-1.5 rounded-md border border-tnvs-border bg-tnvs-surface px-3 py-1.5 text-xs text-tnvs-muted hover:text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Reintentar
            </button>
          </div>
        </Card>
      );
    }
    return this.props.children;
  }
}