import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  label: string;
  className?: string;
};

type State = { failed: boolean };

/** Keeps a renderer or tool failure from taking down the whole workbench. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Do not echo exception content: provider or browser errors can contain
    // environment details. The local fallback is sufficient for the user.
  }

  private retry = () => this.setState({ failed: false });

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className={`component-fallback ${this.props.className ?? ''}`} role="alert">
        <strong>{this.props.label} could not render.</strong>
        <span>The rest of QORE is still available. Retry this panel or reopen the current view.</span>
        <button type="button" className="button secondary small" onClick={this.retry}>
          Retry panel
        </button>
      </div>
    );
  }
}
