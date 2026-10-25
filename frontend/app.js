const $ = (id) => document.getElementById(id);
let selected = null;
const user = () => $('user').value;
const key = () => crypto.randomUUID();
function message(text, error = false) { $('message').textContent = text; $('message').classList.toggle('error', error); }
async function api(path, method = 'GET', body) {
  const headers = { 'X-Demo-User': user() };
  if (method !== 'GET') { headers['Content-Type'] = 'application/json'; headers['Idempotency-Key'] = key(); }
  const response = await fetch('/api/' + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function run(fn) { try { await fn(); message('Updated.'); await refresh(); } catch (error) { message(error.message, true); } }
async function refresh() {
  $('create-panel').classList.toggle('hidden', !['alice', 'bob'].includes(user()));
  if (['alice', 'bob'].includes(user())) {
    const policies = await api('policies');
    $('policy').replaceChildren(...policies.map(p => new Option(`${p.id} · limit ${p.limit_minor}`, p.id)));
  }
  const claims = await api('claims');
  $('claims').replaceChildren(...claims.map(c => {
    const row = document.createElement('button'); row.className = 'claim-row'; row.type = 'button';
    const label = document.createElement('span'); const title = document.createElement('strong'); const sub = document.createElement('small');
    title.textContent = c.policy_id; sub.textContent = `${c.owner} · ${c.requested_minor} DEMO units`;
    label.append(title, sub); const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = c.state;
    row.append(label, badge); row.onclick = () => show(c.id); return row;
  }));
  if (!claims.length) $('claims').textContent = 'No claims yet.';
  if (selected) await show(selected);
}
function fact(label, value) { const box = document.createElement('div'); box.className = 'fact'; const small = document.createElement('small'); const strong = document.createElement('strong'); small.textContent = label; strong.textContent = String(value ?? '—'); box.append(small, strong); return box; }
function button(text, onClick) { const el = document.createElement('button'); el.type = 'button'; el.textContent = text; el.onclick = onClick; return el; }
async function show(id) {
  const c = await api('claims/' + id); selected = id; $('detail-panel').classList.remove('hidden'); $('claim-id').textContent = id.slice(0, 8);
  const root = $('detail'); root.replaceChildren();
  const grid = document.createElement('div'); grid.className = 'grid';
  grid.append(fact('State', c.state), fact('Policy', c.policy_id), fact('Requested', c.requested_minor), fact('Approved', c.approved_minor), fact('Chain', c.chain_status)); root.append(grid);
  const flags = document.createElement('p'); flags.className = 'muted'; flags.textContent = c.fraud_flags.length ? `Review signals: ${c.fraud_flags.join(', ')}` : 'No review signals from the demo rules.'; root.append(flags);
  const actions = document.createElement('div'); actions.className = 'actions'; root.append(actions);
  if (user() === c.owner && c.state === 'Draft') {
    const file = document.createElement('input'); file.type = 'file'; file.accept = '.txt,.pdf,.png,.jpg,.jpeg'; actions.append(file);
    actions.append(button('Add synthetic evidence', () => run(async () => {
      if (!file.files[0]) throw new Error('Choose a file first');
      const f = file.files[0]; const bytes = new Uint8Array(await f.arrayBuffer());
      if (bytes.length > 1048576) throw new Error('Maximum evidence size is 1 MiB');
      let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte);
      await api(`claims/${id}/evidence`, 'POST', { mime: f.type || 'text/plain', content_base64: btoa(binary) });
    })));
    actions.append(button('Submit claim', () => run(() => api(`claims/${id}/submit`, 'POST', {}))));
  }
  if (user() === 'reviewer' && c.state === 'Submitted') actions.append(button('Start review', () => run(() => api(`claims/${id}/review`, 'POST', {}))));
  if (user() === 'reviewer' && c.state === 'UnderReview') {
    const reason = document.createElement('textarea'); reason.placeholder = 'Private decision reason'; actions.append(reason);
    const amount = document.createElement('input'); amount.type = 'number'; amount.min = '1'; amount.max = c.requested_minor; amount.placeholder = 'Approved amount'; actions.append(amount);
    actions.append(button('Approve', () => run(() => api(`claims/${id}/decide`, 'POST', { approve: true, approved_minor: Number(amount.value), reason: reason.value }))));
    actions.append(button('Reject', () => run(() => api(`claims/${id}/decide`, 'POST', { approve: false, approved_minor: 0, reason: reason.value }))));
  }
  if (user() === 'operator' && c.state === 'Approved') {
    const receipt = document.createElement('input'); receipt.placeholder = 'Synthetic receipt reference'; actions.append(receipt);
    actions.append(button('Record simulated settlement', () => run(() => api(`claims/${id}/settle`, 'POST', { receipt: receipt.value }))));
  }
  const heading = document.createElement('h3'); heading.textContent = 'Timeline'; root.append(heading);
  const timeline = document.createElement('div'); timeline.className = 'timeline';
  for (const event of c.events) { const p = document.createElement('p'); p.textContent = `${event.action} · ${event.actor} · ${event.at} UTC`; timeline.append(p); }
  root.append(timeline);
}
$('claim-form').onsubmit = (event) => { event.preventDefault(); run(() => api('claims', 'POST', { policy_id: $('policy').value, requested_minor: Number($('amount').value), incident_date: $('incident').value })); };
$('refresh').onclick = () => run(async () => {});
$('user').onchange = () => { selected = null; $('detail-panel').classList.add('hidden'); message(''); refresh().catch(e => message(e.message, true)); };
$('incident').value = new Date().toISOString().slice(0, 10);
refresh().catch(e => message(e.message, true));
