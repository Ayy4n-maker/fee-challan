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


class _FeePaymentsCollectionWrapper:
    """Add the website Student ID whenever a fee payment is created."""

    def __init__(self, collection_ref, db):
        self._collection_ref = collection_ref
        self._db = db

    def add(self, document_data, *args, **kwargs):
        data = dict(document_data or {})

        student_id = data.get("student_id")

        if student_id and not data.get("student_display_id"):
            try:
                student_doc = (
                    self._db.collection("students")
                    .document(student_id)
                    .get()
                )

                if student_doc.exists:
                    student_data = student_doc.to_dict() or {}
                    serial = student_data.get("serial_id")

                    if serial is not None:
                        try:
                            serial = int(serial)
                            data["student_display_id"] = "%03d" % serial
                        except (ValueError, TypeError):
                            pass
            except Exception as exc:
                print(f"Error setting fee payment student display ID: {exc}")

        return self._collection_ref.add(data, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._collection_ref, name)


class _FirestoreClientWrapper:
    """Delegate to Firestore while adding the fee-payment ID fix."""

    def __init__(self, db):
        self._db = db

    def collection(self, name):
        collection_ref = self._db.collection(name)

        if name == "fee_payments":
            return _FeePaymentsCollectionWrapper(collection_ref, self._db)

        return collection_ref

    def __getattr__(self, name):
        return getattr(self._db, name)


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

        _db = _FirestoreClientWrapper(firestore.client())

    return _db
