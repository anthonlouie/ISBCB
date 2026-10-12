"""One-time conversion of the claude.ai artifact page (inv_sys/artifact/inventory.html) into the
Firebase web app (public/index.html). Kept for reference; edit public/index.html directly from now on."""
import sys
src, out = sys.argv[1], sys.argv[2]
s = open(src).read()

def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:80])
    s = s.replace(a, b)

# ---- page shell: real <head>, config + Firebase layer loaded before the app script
split = s.index("</style>") + len("</style>")
head, body = s[:split], s[split:]
s = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
     '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
     '<meta name="robots" content="noindex">\n' + head + '\n'
     '<script src="firebase-config.js"></script>\n'
     '<script>window.__fbReady = new Promise(r => { window.__resolveFb = r; });\n'
     'window.claude = { use: async name => (await window.__fbReady)(name) };</script>\n'
     '<script type="module" src="firebase-shim.js"></script>\n</head>\n<body>' + body + '\n</body>\n</html>\n')

# ---- stock postings: one Firestore transaction (read item, check, write ledger + balance together)
rep('''async function post({ itemId, type, qty: q, dir, date, cost, party, purpose, ref: refNo, by, remarks, id, extra }) {
  const ref = S.db.doc("items/" + itemId);
  return withLease(ref, async () => {
    if (S.byId.has(id)) throw new Error(`This form was already saved as ${id}.`);
    const snap = await ref.get();''',
'''async function post({ itemId, type, qty: q, dir, date, cost, party, purpose, ref: refNo, by, remarks, id, extra }) {
  if (S.byId.has(id)) throw new Error(`This form was already saved as ${id}.`);
  return S.db.transaction(async tx => {
    const snap = await tx.get("items/" + itemId);''')
rep('''    await appendEntry("ledger", entry);
    const upd = { cur: bal, updatedAt: ts, updatedBy: S.uid };
    if (type === "IN" && cost != null) upd.cost = (it.cost == null || it.cur <= 0) ? cost : Math.round(((it.cur * it.cost) + q * cost) / bal * 10000) / 10000;
    await ref.update(upd);
    return entry;
  });
}''', '''    const upd = { cur: bal, updatedAt: ts, updatedBy: S.uid };
    if (type === "IN" && cost != null) upd.cost = (it.cost == null || it.cur <= 0) ? cost : Math.round(((it.cur * it.cost) + q * cost) / bal * 10000) / 10000;
    const day = localDay();
    tx.set(`ledger/${day}_${S.uid}`, { day, uid: S.uid, entries: { [entry.id]: entry } }, true);
    tx.update("items/" + itemId, upd);
    return entry;
  });
}''')
rep("// The single path for every stock change: lock the item, re-read it, check, write ledger, update balance.",
    "// The single path for every stock change. One transaction: re-read the item, check, write the ledger entry\n// and the new balance together, so they can never disagree.")

# ---- users collection (allow-list) feed
rep('''  live("adjustments", () => db.collection("adjustments").limit(1000), snap => {''',
'''  live("users", () => db.collection("users").limit(500), snap => {
    S.people = new Map(snap.docs.map(d => [d.id, { id: d.id, ...d.data() }])); S.profiles = Object.fromEntries([...S.people].map(([k, v]) => [k, { name: v.name || k }])); changed();
  });
  live("adjustments", () => db.collection("adjustments").limit(1000), snap => {''')
rep('''  try { S.profiles = await S.user.profiles([...ids]); } catch { /* names stay generic */ }''',
    '''  try { Object.assign(S.profiles, await S.user.profiles([...ids])); } catch { /* names stay generic */ }''')

# ---- sign-in identity and role
rep('''  if (!db) { $("#main").innerHTML = `<div class="card"><h2>Sign in to use the inventory</h2><p class="muted">This inventory keeps its data on claude.ai. Open it while signed in to an account it has been shared with.</p></div>`; $("#who").innerHTML = `<span class="muted">Not connected</span>`; return; }
  if (user) {
    S.me = await user.me(); S.uid = S.me.id;
    const write = await user.can("data.write");
    S.role = S.me.isOwner || S.me.canEdit ? "admin" : write === false ? "viewer" : "staff";
  }''', '''  if (!db) return;
  S.me = await user.me(); S.uid = S.me.id; S.role = S.me.role;''')
rep('''if (window.claude?.use) boot(); else $("#main").innerHTML = `<div class="card"><h2>Open this page on claude.ai</h2><p class="muted">The inventory database is only available inside the claude.ai artifact viewer.</p></div>`;''',
    '''boot();''')
rep('''  $("#who").innerHTML = p ? `<img alt="" src="${esc(p.avatarUrl)}"><div><div><b></b></div><div class="muted">${ROLE[S.role]}</div></div>` : `<span class="muted">Not signed in</span>`;''',
    '''  $("#who").innerHTML = p ? `${p.avatarUrl ? `<img alt="" src="${esc(p.avatarUrl)}" referrerpolicy="no-referrer">` : ""}<div style="min-width:0;flex:1"><div><b></b></div><div class="muted">${ROLE[S.role]}</div><button type="button" class="linkbtn" onclick="window.__fbSignOut()">Sign out</button></div>` : `<span class="muted">Not signed in</span>`;''')
rep('.title-links button { border: 0; background: none; padding: 0; color: var(--accent); cursor: pointer; font: inherit; }',
    '.title-links button, .linkbtn { border: 0; background: none; padding: 0; color: var(--accent); cursor: pointer; font: inherit; }\n.linkbtn { font-size: 12.5px; }')
rep('''Ask the artifact's owner to raise your level in the Share menu.''', '''Ask an administrator to change your role under User Access.''')

# ---- User Access: Gmail allow-list management
a = s.index("VIEWS.people = () => {"); b = s.index("async function loadAudit()")
s = s[:a] + r'''VIEWS.people = () => {
  const counts = {}; S.entries.forEach(e => { if (e.uid) counts[e.uid] = (counts[e.uid] || 0) + 1; });
  const users = [...(S.people || new Map()).values()].sort((x, y) => (x.name || x.id).localeCompare(y.name || y.id));
  const admin = isAdmin();
  return head("User Access", "Who can sign in with Google, and what each person can do.") +
  `<div class="grid2"><div class="card"><h2>Roles</h2><div class="tw"><table><thead><tr><th>Role</th><th>Can do</th></tr></thead><tbody>
    <tr><td><b>Administrator</b></td><td>Everything: items, deactivation, stock in/out, approve adjustments, reverse transactions, users, settings, backup &amp; restore.</td></tr>
    <tr><td><b>Inventory Staff</b></td><td>Add and edit items, record stock in/out, request adjustments.</td></tr>
    <tr><td><b>Viewer / Manager</b></td><td>Dashboard, items, history and reports, with exports. No changes.</td></tr></tbody></table></div>
    <p class="small muted">You are signed in as <b>${esc(S.uid)}</b> (${ROLE[S.role]}). Roles are enforced by the database's security rules, not just this page.</p></div>
  ${admin ? `<form class="card" data-form="user-add"><h2>Add a person</h2><div class="form">
    <div class="full"><label for="u-email">Google account email <span class="req">*</span></label><input type="text" id="u-email" name="email" required inputmode="email" autocomplete="off" placeholder="name@gmail.com"></div>
    <div><label for="u-name">Name</label><input type="text" id="u-name" name="name" maxlength="80"></div>
    <div><label for="u-role">Role <span class="req">*</span></label><select id="u-role" name="role">${Object.entries(ROLE).map(([k, v]) => opt(k, v, "staff")).join("")}</select></div>
  </div><div class="row" style="margin-top:14px"><button class="btn primary" type="submit">Give access</button></div><p class="hint">They sign in with this Google account at this web address. Gmail and Google Workspace accounts both work.</p></form>` : "<div></div>"}</div>
  <div class="card"><h2>People with access <span class="muted small">${users.filter(u => u.active !== false).length} active</span></h2><div class="tw"><table><thead><tr><th>Person</th><th>Role</th><th>Status</th><th>Last sign-in</th><th class="num">Movements</th><th></th></tr></thead><tbody>
  ${users.map(u => { const self = u.id === S.uid, locked = u.owner || self || !admin;
    return `<tr><td>${u.photo ? `<img alt="" src="${esc(u.photo)}" referrerpolicy="no-referrer" style="width:22px;height:22px;border-radius:50%;vertical-align:middle;margin-right:6px">` : ""}<b>${esc(u.name || u.id.split("@")[0])}</b>${self ? " <span class='muted'>(you)</span>" : ""}<div class="small muted">${esc(u.id)}</div></td>
    <td>${locked ? esc(ROLE[u.role] || u.role) + (u.owner ? ' <span class="small muted">· owner</span>' : "") : `<select data-user-role="${esc(u.id)}" aria-label="Role for ${esc(u.id)}">${Object.entries(ROLE).map(([k, v]) => opt(k, v, u.role)).join("")}</select>`}</td>
    <td>${pill(u.active === false ? "Inactive" : "Active")}</td><td class="nowrap small">${u.lastLogin ? new Date(u.lastLogin).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "never"}</td>
    <td class="num">${counts[u.id] || 0}</td><td class="num">${locked ? "" : `<button class="btn sm" data-act="user-toggle" data-id="${esc(u.id)}">${u.active === false ? "Restore access" : "Remove access"}</button>`}</td></tr>`; }).join("") || `<tr><td colspan="6" class="empty">No one added yet.</td></tr>`}
  </tbody></table></div></div>
  <div class="card"><h2>Audit trail <button class="btn sm" data-act="load-audit">Load latest</button></h2><div id="audit-box" class="tw">${S.auditHtml || `<p class="muted">Item changes, approvals, reversals, user and settings changes. Stock movements are in Movement History.</p>`}</div></div>`;
};
''' + s[b:]

# ---- Settings: one-click load of the starting item list when the database is empty
rep('''  return head("Settings", "Options, master lists, reconciliation and backups.") +''',
'''  return head("Settings", "Options, master lists, reconciliation and backups.") +
  (S.loaded.items && S.items.size === 0 ? `<div class="card" style="border:2px solid var(--accent)"><h2>Start with the October 2026 item list</h2><p>The database has no items yet. Load the 172 items in 29 categories (zero stock, minimum 0), with categories and storage locations, or restore a backup from the claude.ai version below.</p><button class="btn primary" data-act="seed">Load starting items</button></div>` : "") +''')

# ---- new click / change / submit handlers
rep('''    if (a === "backup" && isAdmin()) {''', '''    if (a === "seed" && isAdmin()) {
      t.disabled = true; const data = await (await fetch("seed.json", { cache: "no-store" })).json(); const total = Object.keys(data).length; let n = 0;
      for (const [path, body] of Object.entries(data)) {
        if (path === "config/settings" && (await S.db.doc(path).get()).exists) { n++; continue; }
        await S.db.doc(path).set(body); if (++n % 10 === 0) t.textContent = `Loading… ${n} of ${total}`;
      }
      await audit("seed_items", { documents: n }); toast(`Loaded ${n - 2} items.`); return;
    }
    if (a === "user-toggle" && isAdmin()) {
      const u = S.people.get(t.dataset.id); const active = u.active === false;
      await S.db.doc("users/" + u.id).update({ active, updatedAt: new Date().toISOString(), updatedBy: S.uid });
      await audit(active ? "restore_user" : "remove_user", { email: u.id }); toast(`${u.id} ${active ? "can sign in again" : "can no longer sign in"}.`); return;
    }
    if (a === "backup" && isAdmin()) {''')
rep('''document.addEventListener("change", ev => {
  const el = ev.target;''', '''document.addEventListener("change", ev => {
  const el = ev.target;
  if (el.dataset.userRole && isAdmin()) {
    const email = el.dataset.userRole, role = el.value;
    S.db.doc("users/" + email).update({ role, updatedAt: new Date().toISOString(), updatedBy: S.uid })
      .then(() => { audit("change_role", { email, role }); toast(`${email} is now ${ROLE[role]}.`); })
      .catch(e => toast(errText(e), "err"));
    return;
  }''')
rep('''    if (kind === "settings") {''', '''    if (kind === "user-add") {
      const email = (d.email || "").toLowerCase().trim();
      if (!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) throw new Error("Enter a valid Google account email address.");
      if (!ROLE[d.role]) throw new Error("Choose a role.");
      const existing = S.people?.get(email);
      await S.db.doc("users/" + email).update({ email, name: d.name || existing?.name || "", role: d.role, active: true,
        ...(existing ? { updatedAt: new Date().toISOString(), updatedBy: S.uid } : { addedAt: new Date().toISOString(), addedBy: S.uid }) });
      await audit(existing ? "change_role" : "add_user", { email, role: d.role });
      toast(`${email} can now sign in as ${ROLE[d.role]}.`); form.reset(); return;
    }
    if (kind === "settings") {''')
rep('''const FIELD_HINTS = [''', '''const FIELD_HINTS = [[/email/i, ["email"]], ''')
open(out, "w").write(s)
print("ok", len(s))
