// Firebase project: bcb-berkeley-inventory. These values identify the project; they are not secret.
// Access is controlled by firestore.rules (owners + the User Access list).
window.FIREBASE_CONFIG = {
  apiKey: "AIzaSyAyETzKzLZnrzWlrMKXZIza0u5MvsRdQf0",
  authDomain: "bcb-berkeley-inventory.firebaseapp.com",
  projectId: "bcb-berkeley-inventory",
  storageBucket: "bcb-berkeley-inventory.firebasestorage.app",
  messagingSenderId: "656701799135",
  appId: "1:656701799135:web:33389f1854d6a7a813076a",
};

// Owner accounts: always administrators, even before anyone is added under User Access.
// Must match the owners() list in firestore.rules (lowercase).
window.OWNER_EMAILS = ["anthonlouie@gmail.com"];
