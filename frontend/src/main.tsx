import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './ErrorBoundary';
import './styles.css';
// Email confirmation can return provider tokens in a URL fragment. QORE uses
// server-owned sessions: discard those tokens and ask for verified email login.
const confirmationFragment = new URLSearchParams(window.location.hash.slice(1));
if (['access_token', 'refresh_token', 'provider_token'].some(key => confirmationFragment.has(key))) {
  const query = new URLSearchParams(window.location.search);
  query.set('email_confirmation', 'opened');
  window.history.replaceState(null, '', window.location.pathname + '?' + query.toString());
}
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary label="QORE workbench" className="root-fallback">
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
