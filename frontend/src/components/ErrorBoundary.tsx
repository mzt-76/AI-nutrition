import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught:', error, info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center gradient-bg">
          <div className="text-center max-w-md px-6">
            <h2 className="text-xl font-semibold text-red-400 mb-3">
              Une erreur est survenue
            </h2>
            <p className="text-muted-foreground mb-4">
              L'application a rencontré un problème inattendu.
            </p>
            <button
              className="px-4 py-2 gradient-green text-white rounded hover:opacity-90"
              onClick={() => {
                this.setState({ hasError: false });
                window.location.href = '/';
              }}
            >
              Recharger l'application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
