import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in UI:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-stone-50 p-6">
          <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-stone-200 p-8 text-center animate-fade-in">
            <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto mb-4 text-2xl">
              🏨
            </div>
            <h2 className="text-xl font-serif font-bold text-stone-900 mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-stone-600 mb-6 leading-relaxed">
              The concierge interface encountered an unexpected display issue. Your session data is intact.
            </p>
            {this.state.error && (
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 mb-6 text-left">
                <p className="text-xs font-mono text-stone-700 break-words">
                  {this.state.error.message}
                </p>
              </div>
            )}
            <button
              onClick={this.handleReset}
              className="w-full py-2.5 px-4 rounded-xl hotel-gradient text-white font-medium text-sm hover:opacity-90 active:scale-95 transition-all shadow-md"
            >
              Refresh Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
