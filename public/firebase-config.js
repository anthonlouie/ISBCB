// 1) Paste the firebaseConfig object from Firebase console → Project settings → Your apps → Web app.
//    These values identify the project; they are not secret. Access is controlled by firestore.rules.
window.FIREBASE_CONFIG = {
  apiKey: "PASTE_API_KEY",
  authDomain: "PASTE_PROJECT_ID.firebaseapp.com",
  projectId: "PASTE_PROJECT_ID",
  storageBucket: "PASTE_PROJECT_ID.appspot.com",
  messagingSenderId: "PASTE_SENDER_ID",
  appId: "PASTE_APP_ID",
};

// 2) Owner accounts: always administrators, even before anyone is added under User Access.
//    Must match the owners() list in firestore.rules.
window.OWNER_EMAILS = ["OWNER_EMAIL@gmail.com"];
