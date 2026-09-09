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
    """Add website Student IDs and support searching by those IDs."""

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

    def where(self, field_path, op_string=None, value=None, **kwargs):
        """Allow the Fee Payments search to use the website Student ID."""

        if (
            field_path == "student_id"
            and op_string == "=="
            and value is not None
        ):
            search_value = str(value).strip()

            # If the submitted value is already a Firestore document ID,
            # preserve the original query behavior.
            try:
                direct_doc = (
                    self._db.collection("students")
                    .document(search_value)
                    .get()
                )
            except Exception:
                direct_doc = None

            if direct_doc is not None and direct_doc.exists:
                return self._collection_ref.where(
                    field_path,
                    op_string,
                    search_value,
                    **kwargs
                )

            # Otherwise treat the value as the website Student ID (001, 002...).
            try:
                serial = int(search_value)
            except (ValueError, TypeError):
                return self._collection_ref.where(
                    field_path,
                    op_string,
                    search_value,
                    **kwargs
                )

            try:
                from flask import session
                current_portfolio_id = session.get(
                    "portfolio_id",
                    "default_portfolio"
                )
            except Exception:
                current_portfolio_id = "default_portfolio"

            students = self._db.collection("students").get()
            matching_student_id = None

            for student_doc in students:
                student_data = student_doc.to_dict() or {}
                student_portfolio = student_data.get("portfolio_id")

                if current_portfolio_id == "default_portfolio":
                    in_portfolio = student_portfolio in (
                        None,
                        "",
                        "default_portfolio"
                    )
                else:
                    in_portfolio = student_portfolio == current_portfolio_id

                if not in_portfolio:
                    continue

                try:
                    student_serial = int(student_data.get("serial_id"))
                except (ValueError, TypeError):
                    continue

                if student_serial == serial:
                    matching_student_id = student_doc.id
                    break

            if matching_student_id:
                return self._collection_ref.where(
                    "student_id",
                    "==",
                    matching_student_id,
                    **kwargs
                )

            # No matching Student ID: keep the original query so it returns
            # no matching payment records instead of raising an error.
            return self._collection_ref.where(
                field_path,
                op_string,
                search_value,
                **kwargs
            )

        return self._collection_ref.where(
            field_path,
            op_string,
            value,
            **kwargs
        )

    def __getattr__(self, name):
        return getattr(self._collection_ref, name)


class _FirestoreClientWrapper:
    """Delegate to Firestore while adding fee-payment ID support."""

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
