# BCB-Berkeley Inventory (Firebase)

The BCB-Berkeley inventory app, running on Google Firebase:

- **Cloud Firestore** holds the data.
- **Firebase Authentication** handles "Sign in with Google" (Gmail or Google Workspace accounts).
- **Firebase Hosting** serves the web address, e.g. `https://<project-id>.web.app`.

It is the same app as the claude.ai artifact version in the `inv_sys` repository: dashboard, items, Stock In / Stock Out with review, adjustments with approval, reversals, movement history, seven reports with Excel/CSV/PDF export, the theme and density switches, and Recent chips. What changes:

| | claude.ai artifact | This version |
|---|---|---|
| **Sign-in** | claude.ai account | Google account (Gmail or Workspace) |
| **Who has access** | the artifact's Share menu | **User Access** page: add an email and pick a role |
| **Role enforcement** | in the page, plus admin-only settings in the database | Firestore **security rules** enforce every role on Google's servers |
| **Stock postings** | lock + two writes | one **Firestore transaction**: the balance and ledger entry commit together or not at all |
| **Hosting** | claude.ai | your own Firebase address (custom domain optional) |

## Layout

```
public/index.html          the app (one page)
public/firebase-shim.js    Google sign-in, access check, Firestore adapter + transactions
public/firebase-config.js  YOUR project config and owner email(s)  ← edit
public/seed.json           starting data: 172 items, 29 categories, locations, settings
firestore.rules            security rules (roles)                  ← edit owner email
firebase.json / .firebaserc  hosting + rules deployment config     ← edit project id
scripts/build_from_artifact.py  one-time converter used to create index.html (reference only)
```

## Setup (one time)

### 1. Firebase project
1. Go to <https://console.firebase.google.com>, sign in with the business Google account and choose **Create a project**. Analytics is optional. Stay on the free **Spark** plan.
2. **Build → Firestore Database → Create database**. Choose a location near your users, e.g. `asia-southeast1` (Singapore); it can't be changed later. Choose **production mode**.
3. **Build → Authentication → Get started → Sign-in method → Google → Enable**, and set a support email.
4. **Project settings → General → Your apps → Web (`</>`)**. Register an app and copy the `firebaseConfig` it shows.

### 2. Fill in this repository
- `public/firebase-config.js`: paste the `firebaseConfig` values, and set `OWNER_EMAILS` to the Google account(s) that should always be administrators.
- `firestore.rules`: put the same owner email(s), **lowercase**, in `owners()`.
- `.firebaserc`: replace `PASTE_PROJECT_ID` with your project id, e.g. `bcb-berkeley-inventory`.

### 3. Deploy (from your computer)
You need Node.js 18 or later (<https://nodejs.org>). Then:

```bash
npm install -g firebase-tools
firebase login                 # opens a browser; sign in with the project's Google account
firebase deploy                # uploads the security rules and the web app
```

The output prints the **Hosting URL**, e.g. `https://bcb-berkeley-inventory.web.app`. Your `*.web.app` and `*.firebaseapp.com` addresses are already approved for Google sign-in. A custom domain needs adding under **Authentication → Settings → Authorized domains** and **Hosting → Add custom domain**.

To publish later changes, run `firebase deploy` again. `firebase deploy --only firestore:rules` updates just the rules; `--only hosting` updates just the app.

### 4. First sign-in
1. Open the Hosting URL and **Sign in with Google** as an owner account.
2. Load your data:
   - **Fresh start:** go to **Settings** and click **Load starting items**. This loads the 172 items with zero stock and minimum 0.
   - **Bring over the claude.ai data:** in the claude.ai version, go to **Settings → Download backup**. Then here, go to **Settings → Restore**, choose that file and type `RESTORE`. Movements recorded on claude.ai keep their quantities, but the person who posted them shows as "Someone", because claude.ai ids aren't email addresses.
3. Go to **User Access** and add each person's Google email with a role (Administrator, Inventory Staff, or Viewer / Manager). They can sign in straight away. **Remove access** blocks them immediately.

## How access works
- **Owners** listed in both `firebase-config.js` and `firestore.rules` are always administrators. They are the way in on day one, and can't be locked out by mistake.
- **Everyone else** needs an active entry in User Access. Anyone else who signs in sees "No access yet", and the database rejects their reads and writes.
- **The rules enforce each role:**
  - Viewers can only read.
  - Staff can create and edit items (except activate/deactivate), post stock in/out to their own daily ledger, and request adjustments.
  - Only administrators can approve or reject adjustments, reverse transactions, change settings and lists, manage users, read the audit trail, and restore backups.

## Costs and limits
For one store, normal use fits within Firebase's free tier, which allows tens of thousands of document reads and writes per day. Check Google's current pricing page. Movements are stored one document per person per day, so a page load reads a few hundred documents, not thousands. Scheduled automatic backups need the pay-as-you-go (Blaze) plan; the manual **Settings → Download backup** works on the free plan.

## Offline behaviour
- **Browsing:** the app keeps a local copy of the data, so pages still open on a flaky connection and catch up when it returns.
- **Saving:** Stock In / Out and adjustments need a connection, because they run as transactions. Without one they show an error instead of saving half a change.
