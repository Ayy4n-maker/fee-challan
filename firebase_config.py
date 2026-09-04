"""
firebase_config.py
==================
Initializes the Firebase Admin SDK and provides a Firestore client.

Setup:
  - On Vercel: set the environment variable FIREBASE_CREDENTIALS_JSON
    to the full JSON content of your Firebase service account key.
  - Locally: place serviceAccountKey.json in the project root, OR
    set FIREBASE_CREDENTIALS_JSON the same way.

The Firestore client is lazily initialized (only once per process).
"""

import os
import json

import firebase_admin
from firebase_admin import credentials, firestore


_db = None


def get_firestore_db():
    """Return a singleton Firestore client."""

    global _db

    if _db is None:

        if not firebase_admin._apps:

            # ----------------------------------------------------------
            # Try env variable first (production / Vercel)
            # ----------------------------------------------------------
            creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

            if creds_json:

                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)

            else:

                # -------------------------------------------------------
                # Fall back to local file (development)
                # -------------------------------------------------------
                base_dir = os.path.dirname(os.path.abspath(__file__))
                key_path = os.path.join(base_dir, "serviceAccountKey.json")
                if not os.path.exists(key_path):
                    alt_path = os.path.join(base_dir, "serviceAccountKey.json.json")
                    if os.path.exists(alt_path):
                        key_path = alt_path

                cred = credentials.Certificate(key_path)

            firebase_admin.initialize_app(cred)

        _db = firestore.client()

    return _db
