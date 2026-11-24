// Sign-in: a server-side session (HttpOnly cookie) plus this tab's CSRF token.
import { useState } from 'react';
import { api } from './api';
import { Refused } from './parts';

export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  return (
    <main className="op-login">
      <div className="op-login__card">
        <p className="op-mark op-mark--big"><i aria-hidden="true" /><b>ConfidenceGuard</b><span>operations</span></p>
        <h1>Sign in</h1>
        <form onSubmit={async (e) => {
          e.preventDefault(); setBusy(true); setError(null);
          try { await api.signIn(name, password); setPassword(''); onSignedIn(); } catch (err) { setError(err); } finally { setBusy(false); }
        }}>
          <label>Name<input name="username" autoComplete="username" value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          <button type="submit" className="op-btn op-btn--primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        {error != null && <Refused error={error} />}
        <p className="op-mono op-login__fine">Session cookie: HttpOnly, SameSite=Strict. Nothing here is sent anywhere but this installation.</p>
      </div>
    </main>
  );
}
