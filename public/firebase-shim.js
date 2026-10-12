// Firebase layer: Google sign-in, access check against the `users` allow-list, and a small adapter
// that gives the app the same database API it used as a claude.ai artifact (doc / collection /
// where / orderBy / limit / get / set / update / onSnapshot), plus real Firestore transactions.
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  initializeFirestore, persistentLocalCache, persistentMultipleTabManager,
  doc, collection, query, where, orderBy, limit, getDoc, getDocs, setDoc, deleteDoc, onSnapshot, runTransaction,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const cfg = window.FIREBASE_CONFIG;
const OWNERS = (window.OWNER_EMAILS || []).map(e => e.toLowerCase());
const main = () => document.getElementById("main");

if (!cfg || !cfg.apiKey || cfg.apiKey.startsWith("PASTE")) {
  main().innerHTML = `<div class="card"><h2>Firebase is not configured yet</h2><p class="muted">Paste your project's <code>firebaseConfig</code> into <code>public/firebase-config.js</code> and deploy again.</p></div>`;
  throw new Error("Missing Firebase config");
}

const app = initializeApp(cfg);
const auth = getAuth(app);
const fs = initializeFirestore(app, { localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() }) });

// ---------------------------------------------------------------- database adapter
const wrapSnap = s => ({ id: s.id, exists: s.exists(), data: () => (s.exists() ? s.data() : undefined), metadata: s.metadata });
const wrapQuery = qs => ({
  docs: qs.docs.map(wrapSnap), size: qs.size, empty: qs.empty, metadata: qs.metadata,
  docChanges: () => qs.docChanges().map(c => ({ type: c.type, doc: wrapSnap(c.doc), oldIndex: c.oldIndex, newIndex: c.newIndex })),
});
// Map Firestore error codes onto the codes the app already handles.
function mapErr(e) {
  const c = e?.code || "";
  const code = c === "permission-denied" ? "invalid_argument" : c === "resource-exhausted" ? "resource_exhausted"
    : c === "unavailable" || c === "deadline-exceeded" ? "unavailable" : c === "unauthenticated" ? "revoked" : "unavailable";
  return Object.assign(new Error(c === "permission-denied" ? "You don't have permission to make this change." : e?.message || String(e)), { code, fbCode: c });
}
const guard = p => p.catch(e => { throw mapErr(e); });

function docRef(path) {
  const r = doc(fs, path);
  return {
    id: r.id, path,
    get: () => guard(getDoc(r)).then(wrapSnap),
    set: data => guard(setDoc(r, data)),
    update: data => guard(setDoc(r, data, { merge: true })), // deep-merges nested maps, like the artifact store
    delete: () => guard(deleteDoc(r)),
    acquire: async () => ({ acquired: true }),                // stock postings use real transactions instead
    onSnapshot: (next, err) => onSnapshot(r, s => next(wrapSnap(s)), e => err && err(mapErr(e))),
    collection: p => collRef(`${path}/${p}`),
  };
}
function collRef(path, cons = []) {
  const base = collection(fs, path);
  const q = () => (cons.length ? query(base, ...cons) : base);
  return {
    path,
    where: (f, op, v) => collRef(path, [...cons, where(f, op, v)]),
    orderBy: (f, dir) => collRef(path, [...cons, orderBy(f, dir)]),
    limit: n => collRef(path, [...cons, limit(n)]),
    doc: id => docRef(id ? `${path}/${id}` : doc(base).path),
    get: () => guard(getDocs(q())).then(wrapQuery),
    onSnapshot: (next, err) => onSnapshot(q(), s => next(wrapQuery(s)), e => err && err(mapErr(e))),
  };
}
const db = {
  doc: docRef,
  collection: p => collRef(p),
  // All-or-nothing: reads and writes inside fn commit together or not at all.
  transaction: fn => runTransaction(fs, tx => fn({
    get: async path => wrapSnap(await tx.get(doc(fs, path))),
    set: (path, data, merge) => tx.set(doc(fs, path), data, merge ? { merge: true } : {}),
    update: (path, data) => tx.set(doc(fs, path), data, { merge: true }),
  })).catch(e => { throw e?.code && !e.fbCode && String(e.code).includes("-") ? mapErr(e) : e; }),
};

// ---------------------------------------------------------------- people
let people = {}; // email -> users doc
function userApi(ctx) {
  return {
    me: async () => ({ id: ctx.email, name: ctx.user.displayName || ctx.email, email: ctx.email, avatarUrl: ctx.user.photoURL || "",
      isOwner: ctx.role === "admin", canEdit: ctx.role === "admin", role: ctx.role }),
    can: async () => ctx.role !== "viewer",
    profiles: async ids => Object.fromEntries([].concat(ids).map(id => [id, { id, name: people[id]?.name || (id.includes("@") ? id.split("@")[0] : ""), avatarUrl: people[id]?.photo || "" }])),
  };
}
const downloads = {
  save: async ({ filename, data }) => {
    const blob = data instanceof Blob ? data : new Blob([data]);
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  },
};

// ---------------------------------------------------------------- sign-in gate
function screen(html) {
  main().innerHTML = `<div class="card" style="max-width:440px;margin:8vh auto;text-align:center">${html}</div>`;
}
function showLogin(msg) {
  screen(`<h1 style="margin-bottom:6px">${document.title}</h1><p class="muted">Inventory management · sign in with your Google account</p>
    ${msg ? `<p class="field-error">${msg}</p>` : ""}
    <button class="btn primary lg" id="g-signin" style="margin-top:12px">Sign in with Google</button>`);
  document.getElementById("g-signin").onclick = async () => {
    const provider = new GoogleAuthProvider(); provider.setCustomParameters({ prompt: "select_account" });
    try { await signInWithPopup(auth, provider); }
    catch (e) {
      if (["auth/popup-blocked", "auth/operation-not-supported-in-this-environment"].includes(e.code)) return signInWithRedirect(auth, provider);
      if (e.code !== "auth/popup-closed-by-user" && e.code !== "auth/cancelled-popup-request") showLogin("Sign-in failed: " + (e.message || e.code));
    }
  };
}
window.__fbSignOut = () => signOut(auth).then(() => location.reload());

let started = false;
onAuthStateChanged(auth, async user => {
  if (!user) { if (started) location.reload(); else showLogin(); return; }
  if (started) return;
  const email = (user.email || "").toLowerCase();
  let role = OWNERS.includes(email) ? "admin" : null;
  try {
    const snap = await getDoc(doc(fs, "users", email));
    if (snap.exists()) {
      const u = snap.data();
      if (!role && u.active !== false && ["admin", "staff", "viewer"].includes(u.role)) role = u.role;
      setDoc(doc(fs, "users", email), { name: user.displayName || u.name || "", photo: user.photoURL || "", lastLogin: new Date().toISOString() }, { merge: true }).catch(() => {});
    } else if (role === "admin") {
      await setDoc(doc(fs, "users", email), { email, name: user.displayName || "", photo: user.photoURL || "", role: "admin", active: true, owner: true, addedAt: new Date().toISOString() });
    }
  } catch (e) { console.warn("profile lookup failed", e); }
  if (!role) {
    screen(`<h2>No access yet</h2><p><b>${email}</b> isn't on the access list for this inventory.</p><p class="muted">Ask an administrator to add this Google account under <b>User Access</b>.</p><button class="btn" id="g-out">Use a different account</button>`);
    document.getElementById("g-out").onclick = window.__fbSignOut;
    return;
  }
  started = true;
  onSnapshot(collection(fs, "users"), s => { people = Object.fromEntries(s.docs.map(d => [d.id, d.data()])); }, () => {});
  const ctx = { user, email, role };
  window.__resolveFb(name => (name === "db" ? db : name === "user" ? userApi(ctx) : name === "downloads" ? downloads : null));
});
