// Admin (proposal step 4): principals and roles, tokens, notification channels and rules, the egress allowlist,
// retention and pins, and the audit chain. Secrets are shown once, in a box the administrator dismisses; nothing
// here can read them again. Every change is written to the hash-chained audit log by the server.
// Everyone can change their own password at the top; the rest needs the admin permission.
import { useState } from 'react';
import { api, type Session } from './api';
import { Action, Empty, Loading, Refused, useResource, when, words } from './parts';

interface Binding { role: string; scope_kind: string; scope_id: string }
interface PrincipalRow { id: string; kind: 'user' | 'service'; name: string; disabled: boolean; created_at: string; has_password: boolean; last_seen: string | null; live_tokens: number; roles: Binding[] }
interface PrincipalsView { items: PrincipalRow[]; roles: Record<string, string[]>; service_forbidden_roles: string[] }
interface TokenRow { id: string; principal: string; kind: string; scopes: string[]; created_at: string; expires_at: string | null; revoked_at: string | null; last_used_at: string | null; expired: boolean }
interface ChannelsView { channels: { id: string; kind: string; destination: string; config: Record<string, unknown>; enabled: boolean; created_at: string }[]; rules: { id: string; channel_id: string; deployment_id: string | null; min_priority: string; digest_seconds: number | null; quiet: [string, string][]; escalation_level: number }[]; outbox: Record<string, number> }
interface EgressView { items: { id: string; scheme: string; host: string; port: number; cidr: string | null; created_at: string }[]; statement: string }
interface RetentionView { system: string; observation_days: number; default: boolean; updated_at: string | null; pins: { id: string; holder_kind: string; holder_id: string; reason: string; start_tick: string; end_tick: string; expires_at: string | null; released_at: string | null; created_by: string; live: boolean }[]; statement: string }
interface AuditView { items: { seq: number; at: string; actor: string; action: string; target: string; payload: Record<string, unknown>; hash: string }[]; cursor: number | null }
interface Verify { chain_ok: boolean; first_bad_seq: number | null; entries: number; head: string | null; anchors: { seq: number; sink: string; exported_at: string; matches: boolean }[]; anchors_ok: boolean; statement: string }

const TABS = ['principals', 'tokens', 'notifications', 'egress', 'retention', 'audit'] as const;
type Tab = (typeof TABS)[number];

export function Admin({ session }: { session: Session }) {
  const [tab, setTab] = useState<Tab>('principals');
  const admin = session.permissions.includes('admin');
  return (
    <>
      <section className="op-head">
        <span className="op-k">Admin</span>
        <h1>Access, delivery, retention and audit</h1>
        <p>Every change here is recorded in the hash-chained audit log. Passwords, token secrets and signing keys are shown once and stored only as
          hashes or in the secrets store; no one can read them back.</p>
      </section>
      <OwnPassword session={session} />
      {!admin ? <p className="op-mono">The rest of this area needs the admin permission.</p> : (
        <>
          <div className="op-seg" role="tablist" aria-label="Admin areas">
            {TABS.map((t) => <button key={t} type="button" role="tab" aria-selected={tab === t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t}</button>)}
          </div>
          {tab === 'principals' && <Principals me={session.principal.name} />}
          {tab === 'tokens' && <Tokens />}
          {tab === 'notifications' && <Notifications />}
          {tab === 'egress' && <Egress />}
          {tab === 'retention' && <Retention />}
          {tab === 'audit' && <Audit />}
        </>)}
    </>
  );
}

/** A secret shown exactly once. Dismissing it drops it from memory; the server cannot show it again. */
function OneTime({ label, value, onDismiss }: { label: string; value: string; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="op-onetime" role="status">
      <span className="op-k">{label} · shown once</span>
      <code className="op-mono">{value}</code>
      <div className="op-acts">
        <button type="button" className="op-btn" onClick={async () => { try { await navigator.clipboard.writeText(value); setCopied(true); } catch { setCopied(false); } }}>{copied ? 'Copied' : 'Copy'}</button>
        <button type="button" className="op-btn op-btn--primary" onClick={onDismiss}>I have stored it</button>
      </div>
    </div>
  );
}

function OwnPassword({ session }: { session: Session }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [done, setDone] = useState(false);
  if (session.principal.kind !== 'user') return null;
  return (
    <section className="op-sec">
      <h2>Your password</h2>
      <form className="op-form" onSubmit={(e) => e.preventDefault()}>
        <input type="text" name="username" autoComplete="username" value={session.principal.name} readOnly hidden />
        <label>Current<input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></label>
        <label>New (at least 12 characters)<input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></label>
        <Action label="Change password" disabled={!api.canMutate() || !current || next.length < 12}
          run={async () => { await api.post('/session/password', { current, new: next }); setCurrent(''); setNext(''); setDone(true); }} />
      </form>
      {done && <p className="op-ok">Changed. Your other sessions were signed out.</p>}
    </section>
  );
}

function Principals({ me }: { me: string }) {
  const view = useResource<PrincipalsView>('/principals');
  const [kind, setKind] = useState<'user' | 'service'>('user');
  const [name, setName] = useState('');
  const [role, setRole] = useState('viewer');
  const [secret, setSecret] = useState<{ label: string; value: string } | null>(null);
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="principals" />;
  const roles = Object.keys(view.data.roles);
  const forbidden = view.data.service_forbidden_roles;
  return (
    <>
      {secret && <OneTime label={secret.label} value={secret.value} onDismiss={() => setSecret(null)} />}
      <section className="op-sec">
        <h2>Add a principal</h2>
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>Kind<select value={kind} onChange={(e) => setKind(e.target.value as 'user' | 'service')}><option value="user">user (password)</option><option value="service">service (tokens only)</option></select></label>
          <label>Name<input value={name} onChange={(e) => setName(e.target.value.trim())} placeholder="e.g. dana" /></label>
          <label>Role<select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">none</option>{roles.map((r) => <option key={r} value={r} disabled={kind === 'service' && forbidden.includes(r)}>{words(r)}</option>)}</select></label>
          <Action label="Create" tone="primary" disabled={!api.canMutate() || !name}
            run={async () => {
              const r = await api.post<{ name: string; initial_password: string | null }>('/principals', { kind, name, roles: role ? [role] : [] });
              if (r.initial_password) setSecret({ label: `Initial password for ${r.name}`, value: r.initial_password });
              setName('');
            }} onDone={view.reload} />
        </form>
        <p className="op-mono">Service principals cannot hold {forbidden.map(words).join(' or ')} (separation of duties). No role can execute production changes.</p>
      </section>
      <section className="op-sec">
        <h2>Principals</h2>
        <div className="op-scroll">
          <table className="op-table">
            <thead><tr><th>Principal</th><th>Roles</th><th>Credentials</th><th>Last seen</th><th /></tr></thead>
            <tbody>{view.data.items.map((p) => <PrincipalRowView key={p.id} p={p} me={me} roles={roles} forbidden={forbidden} onDone={view.reload} onSecret={setSecret} />)}</tbody>
          </table>
        </div>
        <details className="op-details"><summary>What each role permits</summary>
          <table className="op-table op-table--tight"><tbody>{Object.entries(view.data.roles).map(([r, perms]) => <tr key={r}><td>{words(r)}</td><td className="op-mono">{perms.join(' · ')}</td></tr>)}</tbody></table>
        </details>
      </section>
    </>
  );
}

function PrincipalRowView({ p, me, roles, forbidden, onDone, onSecret }: { p: PrincipalRow; me: string; roles: string[]; forbidden: string[]; onDone: () => void; onSecret: (s: { label: string; value: string }) => void }) {
  const [role, setRole] = useState('');
  const [scope, setScope] = useState('');
  const bind = (action: 'bind' | 'unbind', b: Binding) => api.post(`/principals/${p.id}/roles`, { action, ...b });
  return (
    <tr className={p.disabled ? 'op-muted-row' : ''}>
      <td><b>{p.name}</b>{p.name === me ? ' (you)' : ''}<br /><span className="op-mono">{p.kind}{p.disabled ? ' · disabled' : ''} · since {when(p.created_at)}</span></td>
      <td>
        <ul className="op-chips">{p.roles.length === 0 ? <li className="op-mono">no roles</li> : p.roles.map((b) => (
          <li key={`${b.role}:${b.scope_kind}:${b.scope_id}`}><span className="op-mono">{words(b.role)}{b.scope_kind !== 'org' ? ` @ ${b.scope_kind} ${b.scope_id}` : ''}</span>
            <Action label="×" title={`Remove ${b.role}`} run={() => bind('unbind', b)} onDone={onDone} disabled={!api.canMutate()} /></li>))}</ul>
        <span className="op-inline">
          <select aria-label={`Role to add for ${p.name}`} value={role} onChange={(e) => setRole(e.target.value)}><option value="">add role…</option>
            {roles.map((r) => <option key={r} value={r} disabled={p.kind === 'service' && forbidden.includes(r)}>{words(r)}</option>)}</select>
          <input aria-label="Deployment scope (optional)" placeholder="deployment (optional)" value={scope} onChange={(e) => setScope(e.target.value.trim())} />
          <Action label="Add" disabled={!api.canMutate() || !role} run={async () => { await bind('bind', scope ? { role, scope_kind: 'deployment', scope_id: scope } : { role, scope_kind: 'org', scope_id: '' }); setRole(''); setScope(''); }} onDone={onDone} />
        </span>
      </td>
      <td className="op-mono">{p.kind === 'user' ? (p.has_password ? 'password set' : 'no password') : 'no password'} · {p.live_tokens} live token{p.live_tokens === 1 ? '' : 's'}</td>
      <td className="op-mono">{when(p.last_seen)}</td>
      <td className="op-stack">
        {p.kind === 'user' && <Action label="Reset password" disabled={!api.canMutate()} run={async () => { const r = await api.post<{ password: string }>(`/principals/${p.id}/password`); onSecret({ label: `New password for ${p.name}`, value: r.password }); }} onDone={onDone} />}
        <Action label={p.disabled ? 'Enable' : 'Disable'} title={p.disabled ? undefined : 'Signs out its sessions and revokes its tokens'} disabled={!api.canMutate()} run={() => api.post(`/principals/${p.id}/disable`, { disabled: !p.disabled })} onDone={onDone} />
      </td>
    </tr>
  );
}

function Tokens() {
  const tokens = useResource<{ items: TokenRow[] }>('/tokens');
  const principals = useResource<PrincipalsView>('/principals');
  const [principal, setPrincipal] = useState('');
  const [scopes, setScopes] = useState('');
  const [days, setDays] = useState('90');
  const [secret, setSecret] = useState<string | null>(null);
  if (tokens.error) return <Refused error={tokens.error} />;
  if (!tokens.data || !principals.data) return <Loading what="tokens" />;
  const live = (t: TokenRow) => !t.revoked_at && !t.expired;
  return (
    <>
      {secret && <OneTime label="API token" value={secret} onDismiss={() => setSecret(null)} />}
      <section className="op-sec">
        <h2>Issue a token</h2>
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>Principal<select value={principal} onChange={(e) => setPrincipal(e.target.value)}><option value="">choose…</option>
            {principals.data.items.filter((p) => !p.disabled).map((p) => <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>)}</select></label>
          <label>Scopes (comma-separated)<input value={scopes} onChange={(e) => setScopes(e.target.value)} placeholder="ingest:source:scorecard-events" /></label>
          <label>Expires after (days)<input inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ''))} placeholder="never" /></label>
          <Action label="Issue" tone="primary" disabled={!api.canMutate() || !principal || !scopes.trim()}
            run={async () => { const r = await api.post<{ token: string }>('/tokens', { principal, scopes: scopes.split(',').map((s) => s.trim()).filter(Boolean), expires_in_days: days || null }); setSecret(r.token); setScopes(''); }} onDone={tokens.reload} />
        </form>
        <p className="op-mono">Scopes: role:&lt;role&gt; (narrows the principal's own roles, never widens them) · ingest:source:&lt;id&gt; (service principals only) · read:deployment:&lt;id&gt;.</p>
      </section>
      <section className="op-sec">
        <h2>Tokens</h2>
        {tokens.data.items.length === 0 ? <Empty>No tokens have been issued.</Empty> : (
          <div className="op-scroll"><table className="op-table op-table--tight">
            <thead><tr><th>Principal</th><th>Scopes</th><th>Issued</th><th>Expires</th><th>Last used</th><th>State</th><th /></tr></thead>
            <tbody>{tokens.data.items.map((t) => <tr key={t.id} className={live(t) ? '' : 'op-muted-row'}>
              <td>{t.principal}<br /><span className="op-mono">{t.kind} · {t.id.slice(0, 8)}</span></td><td className="op-mono">{t.scopes.join(' · ')}</td>
              <td className="op-mono">{when(t.created_at)}</td><td className="op-mono">{t.expires_at ? when(t.expires_at) : 'never'}</td><td className="op-mono">{when(t.last_used_at)}</td>
              <td>{t.revoked_at ? `revoked ${when(t.revoked_at)}` : t.expired ? 'expired' : 'live'}</td>
              <td>{live(t) && <Action label="Revoke" disabled={!api.canMutate()} run={() => api.post(`/tokens/${t.id}/revoke`)} onDone={tokens.reload} />}</td></tr>)}</tbody>
          </table></div>)}
      </section>
    </>
  );
}

function Notifications() {
  const view = useResource<ChannelsView>('/channels');
  const deployments = useResource<{ id: string }[]>('/deployments');
  const [channel, setChannel] = useState({ id: '', kind: 'webhook', destination: '', from: '', to: '' });
  const [rule, setRule] = useState({ id: '', channel: '', deployment: '', min_priority: 'P2', digest: '' });
  const [secret, setSecret] = useState<string | null>(null);
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="channels" />;
  return (
    <>
      {secret && <OneTime label="Webhook signing key (HMAC-SHA256)" value={secret} onDismiss={() => setSecret(null)} />}
      <section className="op-sec">
        <h2>Channels</h2>
        <p className="op-mono">Outbox: {Object.entries(view.data.outbox).map(([k, v]) => `${k} ${v}`).join(' · ') || 'empty'}{view.data.outbox.dead ? ' · dead letters raise a monitoring-health condition' : ''}</p>
        {view.data.channels.length === 0 ? <Empty>No channels. Incidents are recorded but no one is notified.</Empty> : (
          <table className="op-table op-table--tight"><thead><tr><th>Channel</th><th>Kind</th><th>Destination</th><th>State</th></tr></thead>
            <tbody>{view.data.channels.map((c) => <tr key={c.id}><td className="op-mono">{c.id}</td><td>{c.kind}</td><td className="op-mono">{c.destination}{c.kind === 'smtp' ? ` · ${String(c.config.to ?? '')}` : ''}</td><td>{c.enabled ? 'enabled' : 'disabled'}</td></tr>)}</tbody></table>)}
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>Id<input value={channel.id} onChange={(e) => setChannel({ ...channel, id: e.target.value.trim() })} placeholder="oncall-hook" /></label>
          <label>Kind<select value={channel.kind} onChange={(e) => setChannel({ ...channel, kind: e.target.value })}><option value="webhook">webhook</option><option value="smtp">smtp</option></select></label>
          <label>Destination<input value={channel.destination} onChange={(e) => setChannel({ ...channel, destination: e.target.value.trim() })} placeholder={channel.kind === 'webhook' ? 'the https URL of your receiver' : 'smtps, then host and port'} /></label>
          {channel.kind === 'smtp' && <><label>From<input value={channel.from} onChange={(e) => setChannel({ ...channel, from: e.target.value.trim() })} /></label>
            <label>To<input value={channel.to} onChange={(e) => setChannel({ ...channel, to: e.target.value.trim() })} /></label></>}
          <Action label="Add channel" tone="primary" disabled={!api.canMutate() || !channel.id || !channel.destination}
            run={async () => {
              const r = await api.post<{ signing_key: string | null }>('/channels', { id: channel.id, kind: channel.kind, destination: channel.destination, config: channel.kind === 'smtp' ? { from: channel.from, to: channel.to } : {} });
              if (r.signing_key) setSecret(r.signing_key);
              setChannel({ id: '', kind: 'webhook', destination: '', from: '', to: '' });
            }} onDone={view.reload} />
        </form>
        <p className="op-mono">Destinations must also be on the egress allowlist. SMTP credentials are never taken in the browser: supply them from a script with POST /api/ops/v1/channels (credentials field).</p>
      </section>
      <section className="op-sec">
        <h2>Rules</h2>
        {view.data.rules.length === 0 ? <Empty>No rules.</Empty> : (
          <table className="op-table op-table--tight"><thead><tr><th>Rule</th><th>Channel</th><th>Deployment</th><th>At or above</th><th>Digest</th><th>Escalation</th></tr></thead>
            <tbody>{view.data.rules.map((r) => <tr key={r.id}><td className="op-mono">{r.id}</td><td className="op-mono">{r.channel_id}</td><td className="op-mono">{r.deployment_id ?? 'every deployment'}</td><td className="op-mono">{r.min_priority}</td><td className="op-mono">{r.digest_seconds ? `${r.digest_seconds / 60} min` : 'immediate'}</td><td className="op-mono">{r.escalation_level || 'first notice'}</td></tr>)}</tbody></table>)}
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>Id<input value={rule.id} onChange={(e) => setRule({ ...rule, id: e.target.value.trim() })} placeholder="p2-oncall" /></label>
          <label>Channel<select value={rule.channel} onChange={(e) => setRule({ ...rule, channel: e.target.value })}><option value="">choose…</option>{view.data.channels.map((c) => <option key={c.id} value={c.id}>{c.id}</option>)}</select></label>
          <label>Deployment<select value={rule.deployment} onChange={(e) => setRule({ ...rule, deployment: e.target.value })}><option value="">every deployment</option>{(deployments.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.id}</option>)}</select></label>
          <label>At or above<select value={rule.min_priority} onChange={(e) => setRule({ ...rule, min_priority: e.target.value })}>{['P1', 'P2', 'P3', 'P4'].map((p) => <option key={p}>{p}</option>)}</select></label>
          <label>Digest (minutes, optional)<input inputMode="numeric" value={rule.digest} onChange={(e) => setRule({ ...rule, digest: e.target.value.replace(/\D/g, '') })} /></label>
          <Action label="Add rule" disabled={!api.canMutate() || !rule.id || !rule.channel}
            run={async () => { await api.post('/rules', { id: rule.id, channel: rule.channel, deployment: rule.deployment || null, min_priority: rule.min_priority, digest_seconds: rule.digest ? Number(rule.digest) * 60 : null }); setRule({ id: '', channel: '', deployment: '', min_priority: 'P2', digest: '' }); }} onDone={view.reload} />
        </form>
        <p className="op-mono">Notices go out on state and priority changes only, carry ids, priority and links (never evidence values), and P1 is never held by a digest or quiet window.</p>
      </section>
    </>
  );
}

function Egress() {
  const view = useResource<EgressView>('/egress');
  const [entry, setEntry] = useState({ scheme: 'https', host: '', port: '', cidr: '' });
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="the egress allowlist" />;
  return (
    <section className="op-sec">
      <h2>Egress allowlist</h2>
      <p className="op-muted">{view.data.statement}</p>
      {view.data.items.length === 0 ? <Empty>Nothing is allowed. Notifications cannot leave this installation.</Empty> : (
        <table className="op-table op-table--tight"><thead><tr><th>Destination</th><th>Resolved address must be in</th><th>Added</th><th /></tr></thead>
          <tbody>{view.data.items.map((e) => <tr key={e.id}><td className="op-mono">{e.scheme}://{e.host}:{e.port}</td><td className="op-mono">{e.cidr ?? 'any public address'}</td><td className="op-mono">{when(e.created_at)}</td>
            <td><Action label="Remove" disabled={!api.canMutate()} run={() => api.post(`/egress/${e.id}/remove`)} onDone={view.reload} /></td></tr>)}</tbody></table>)}
      <form className="op-form" onSubmit={(e) => e.preventDefault()}>
        <label>Scheme<select value={entry.scheme} onChange={(e) => setEntry({ ...entry, scheme: e.target.value })}>{['https', 'smtps', 'smtp', 'http'].map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Host<input value={entry.host} onChange={(e) => setEntry({ ...entry, host: e.target.value.trim() })} placeholder="hooks.example.com" /></label>
        <label>Port<input inputMode="numeric" value={entry.port} onChange={(e) => setEntry({ ...entry, port: e.target.value.replace(/\D/g, '') })} placeholder="default" /></label>
        <label>CIDR (optional)<input value={entry.cidr} onChange={(e) => setEntry({ ...entry, cidr: e.target.value.trim() })} placeholder="203.0.113.0/24" /></label>
        <Action label="Allow" tone="primary" disabled={!api.canMutate() || !entry.host}
          run={async () => { await api.post('/egress', { scheme: entry.scheme, host: entry.host, port: entry.port ? Number(entry.port) : null, cidr: entry.cidr || null }); setEntry({ scheme: 'https', host: '', port: '', cidr: '' }); }} onDone={view.reload} />
      </form>
      {entry.scheme === 'http' && <p className="op-refused">Plain http sends notices unencrypted. Prefer https.</p>}
    </section>
  );
}

function Retention() {
  const systems = useResource<{ id: string; name: string }[]>('/systems');
  const [system, setSystem] = useState<string | null>(null);
  if (systems.error) return <Refused error={systems.error} />;
  if (!systems.data) return <Loading what="systems" />;
  if (systems.data.length === 0) return <Empty>No systems are registered.</Empty>;
  const chosen = system ?? systems.data[0].id;
  return (
    <>
      {systems.data.length > 1 && <div className="op-seg" role="group" aria-label="System">{systems.data.map((s) => <button key={s.id} type="button" aria-pressed={s.id === chosen} onClick={() => setSystem(s.id)}>{s.id}</button>)}</div>}
      <SystemRetention key={chosen} system={chosen} />
    </>
  );
}

function SystemRetention({ system }: { system: string }) {
  const view = useResource<RetentionView>(`/systems/${system}/retention`);
  const [days, setDays] = useState('');
  const [pin, setPin] = useState({ start: '', end: '', reason: '', expires: '' });
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="retention" />;
  const iso = (d: string) => (d ? new Date(`${d}T00:00:00Z`).toISOString() : '');
  const tickDate = (t: string) => new Date(Number(t) / 1e6).toISOString().slice(0, 10);
  return (
    <>
      <section className="op-sec">
        <h2>Observation retention · {system}</h2>
        <p className="op-muted">{view.data.statement}</p>
        <p><b className="op-mono">{view.data.observation_days} days</b> {view.data.default ? '(the default)' : `· set ${when(view.data.updated_at)}`}</p>
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>New retention (days, at least 30)<input inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ''))} /></label>
          <Action label="Set retention" disabled={!api.canMutate() || !days || Number(days) < 30} run={async () => { await api.post(`/systems/${system}/retention`, { observation_days: Number(days) }); setDays(''); }} onDone={view.reload} />
        </form>
      </section>
      <section className="op-sec">
        <h2>Pins</h2>
        {view.data.pins.length === 0 ? <Empty>No pins. Retention would purge everything older than the policy.</Empty> : (
          <div className="op-scroll"><table className="op-table op-table--tight"><thead><tr><th>Holder</th><th>Event time</th><th>Reason</th><th>Until</th><th>State</th></tr></thead>
            <tbody>{view.data.pins.map((p) => <tr key={p.id} className={p.live ? '' : 'op-muted-row'}><td className="op-mono">{p.holder_kind}<br />{p.holder_id.slice(0, 18)}</td><td className="op-mono">{tickDate(p.start_tick)} → {tickDate(p.end_tick)}</td>
              <td>{p.reason}</td><td className="op-mono">{p.expires_at ? when(p.expires_at) : p.holder_kind === 'incident' ? 'while open, then 90 days' : 'while held'}</td><td>{p.released_at ? `released ${when(p.released_at)}` : p.live ? 'live' : 'expired'}</td></tr>)}</tbody></table></div>)}
        <form className="op-form" onSubmit={(e) => e.preventDefault()}>
          <label>From (event date)<input type="date" value={pin.start} onChange={(e) => setPin({ ...pin, start: e.target.value })} /></label>
          <label>To (exclusive)<input type="date" value={pin.end} onChange={(e) => setPin({ ...pin, end: e.target.value })} /></label>
          <label>Reason<input value={pin.reason} onChange={(e) => setPin({ ...pin, reason: e.target.value })} placeholder="regulator inquiry" /></label>
          <label>Expires<input type="date" value={pin.expires} onChange={(e) => setPin({ ...pin, expires: e.target.value })} /></label>
          <Action label="Pin" disabled={!api.canMutate() || !pin.start || !pin.end || !pin.reason || !pin.expires}
            run={async () => { await api.post(`/systems/${system}/pins`, { start: iso(pin.start), end: iso(pin.end), reason: pin.reason, expires_at: iso(pin.expires) }); setPin({ start: '', end: '', reason: '', expires: '' }); }} onDone={view.reload} />
        </form>
        <p className="op-mono">Analyst pins always carry an expiry. Incident and proposal pins are created and released automatically.</p>
      </section>
    </>
  );
}

function Audit() {
  const [cursor, setCursor] = useState<number | null>(null);
  const log = useResource<AuditView>(`/audit?limit=50${cursor ? `&cursor=${cursor}` : ''}`);
  const [result, setResult] = useState<Verify | null>(null);
  return (
    <>
      <section className="op-sec">
        <h2>Audit chain</h2>
        <div className="op-acts"><Action label="Verify the chain" tone="primary" disabled={!api.canMutate()} run={async () => setResult(await api.post<Verify>('/audit/verify'))} /></div>
        {result && (
          <div className={`op-verify ${result.chain_ok && result.anchors_ok ? 'is-ok' : 'is-bad'}`} role="status">
            <p><b>{result.chain_ok ? `Chain intact: ${result.entries} entries recompute to the stored head.` : `Chain broken at entry ${result.first_bad_seq}.`}</b></p>
            <p className="op-mono">head {result.head?.slice(0, 24) ?? '—'}… · {result.anchors.length === 0 ? 'no anchors exported yet' : `${result.anchors.length} anchor${result.anchors.length === 1 ? '' : 's'} ${result.anchors_ok ? 'match' : 'do not all match'} · last at entry ${result.anchors[0].seq}, ${when(result.anchors[0].exported_at)}`}</p>
            <p className="op-muted">{result.statement}</p>
          </div>)}
      </section>
      <section className="op-sec">
        <h2>Log</h2>
        {log.error != null ? <Refused error={log.error} /> : !log.data ? <Loading what="the audit log" /> : log.data.items.length === 0 ? <Empty>No entries.</Empty> : (
          <>
            <div className="op-scroll"><table className="op-table op-table--tight">
              <thead><tr><th>#</th><th>At</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
              <tbody>{log.data.items.map((e) => <tr key={e.seq}><td className="op-mono">{e.seq}</td><td className="op-mono">{when(e.at)}</td><td className="op-mono">{e.actor.replace(/^principal:/, '')}</td>
                <td>{words(e.action.replace(/\./g, ' '))}</td><td className="op-mono">{e.target.length > 20 ? `${e.target.slice(0, 18)}…` : e.target}</td>
                <td className="op-mono">{Object.entries(e.payload).map(([k, v]) => `${k} ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ').slice(0, 140) || '—'}</td></tr>)}</tbody>
            </table></div>
            <div className="op-acts">
              {cursor != null && <button type="button" className="op-btn" onClick={() => setCursor(null)}>Newest</button>}
              {log.data.cursor != null && <button type="button" className="op-btn" onClick={() => setCursor(log.data!.cursor)}>Older</button>}
            </div>
          </>)}
      </section>
    </>
  );
}
