from flask import Flask, render_template, request, redirect, url_for, session
from datetime import date, timedelta
import os
from functools import wraps

from firebase_config import get_firestore_db


app = Flask(__name__)


# ==========================================================
# SECRET KEY  (set SECRET_KEY env variable in production)
# ==========================================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "IESC_FEE_SYSTEM_SECRET_KEY_2026"
)


# ==========================================================
# LOGIN DETAILS
# Set these as environment variables in Vercel / production.
# CHANGE THE DEFAULTS before deploying.
# ==========================================================

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

STAFF_USERNAME = os.environ.get("STAFF_USERNAME", "staff")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "staff123")


# ==========================================================
# HELPER — short display ID from Firestore document ID
# ==========================================================

def short_id(doc_id):
    """Return the first 8 characters of a Firestore document ID."""
    return str(doc_id)[:8].upper()


# ==========================================================
# HELPER — convert Firestore document snapshot to dict
# ==========================================================

def doc_to_dict(doc):
    """Convert a Firestore DocumentSnapshot to a plain dict with 'id' field."""
    d = doc.to_dict()
    d["id"] = doc.id
    return d


def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if session.get("admin_logged_in") is not True:

            return redirect(
                url_for("admin_login")
            )

        return function(*args, **kwargs)

    return decorated_function


def staff_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if session.get("staff_logged_in") is not True:

            return redirect(
                url_for("staff_login")
            )

        return function(*args, **kwargs)

    return decorated_function


def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if not (session.get("admin_logged_in") is True or session.get("staff_logged_in") is True):

            return redirect(
                url_for("home")
            )

        return function(*args, **kwargs)

    return decorated_function




# ==========================================================
# HOME / ROLE SELECTION
# ==========================================================

@app.route("/")
def home():

    return render_template(
        "role_selection.html"
    )


# ==========================================================
# ADMIN LOGIN
# ==========================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session.clear()
            session["admin_logged_in"] = True

            return redirect(
                url_for("admin")
            )

        return render_template(
            "admin_login.html",
            error="Invalid admin username or password."
        )

    return render_template(
        "admin_login.html"
    )


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin")
@admin_required
def admin():

    db = get_firestore_db()

    # ----------------------------------------------------------
    # COUNT STUDENTS
    # ----------------------------------------------------------

    students_docs = db.collection("students").get()
    total_students = len(students_docs)

    # ----------------------------------------------------------
    # PAYMENT STATS — fetch all payments once and aggregate
    # ----------------------------------------------------------

    payments_docs = db.collection("fee_payments").get()

    total_received = 0.0
    total_paid = 0
    total_unpaid = 0
    total_late_fee = 0.0

    for doc in payments_docs:

        p = doc.to_dict()
        status = p.get("status", "UNPAID")

        if status == "PAID":

            total_received += float(
                p.get("amount_received") or 0
            )

            total_paid += 1

            total_late_fee += float(
                p.get("late_fee") or 0
            )

        else:

            total_unpaid += 1

    return render_template(
        "admin.html",

        total_students=total_students,

        total_received=total_received,

        total_paid=total_paid,

        total_unpaid=total_unpaid,

        total_late_fee=total_late_fee
    )


# ==========================================================
# ADMIN LOGOUT
# ==========================================================

@app.route("/admin-logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ==========================================================
# STAFF LOGIN
# ==========================================================

@app.route(
    "/staff-login",
    methods=["GET", "POST"]
)
def staff_login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if (
            username == STAFF_USERNAME
            and password == STAFF_PASSWORD
        ):

            session.clear()
            session["staff_logged_in"] = True

            return redirect(
                url_for("staff")
            )

        return render_template(
            "staff_login.html",
            error="Invalid staff username or password."
        )

    return render_template(
        "staff_login.html"
    )


# ==========================================================
# STAFF PORTAL
# ==========================================================

@app.route("/staff")
@staff_required
def staff():

    db = get_firestore_db()

    total_students = len(
        db.collection("students").get()
    )

    return render_template(
        "index.html",
        total_students=total_students
    )


# ==========================================================
# STAFF LOGOUT
# ==========================================================

@app.route("/staff-logout")
def staff_logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ==========================================================
# STUDENTS
# ==========================================================

@app.route("/students")
@login_required
def students():

    db = get_firestore_db()

    docs = db.collection("students").get()

    student_list = [
        doc_to_dict(doc)
        for doc in docs
    ]

    # Sort by class (numeric) then by name
    student_list.sort(
        key=lambda s: (
            int(s.get("class_name") or 0),
            s.get("student_name") or ""
        )
    )

    return render_template(
        "students.html",
        students=student_list
    )


# ==========================================================
# GENERATE CHALLAN LIST
# STUDENT ID SEARCH
# ==========================================================

@app.route("/generate-challan")
@login_required
def generate_challan_list():

    search_id = request.args.get(
        "student_id", ""
    ).strip()

    db = get_firestore_db()

    if search_id:

        # Search by Firestore document ID (exact match)
        doc = db.collection("students").document(search_id).get()

        if doc.exists:
            student_list = [doc_to_dict(doc)]
        else:
            student_list = []

    else:

        docs = db.collection("students").get()

        student_list = [
            doc_to_dict(doc)
            for doc in docs
        ]

        student_list.sort(
            key=lambda s: (
                int(s.get("class_name") or 0),
                s.get("student_name") or ""
            )
        )

    return render_template(
        "generate_challan_list.html",
        students=student_list,
        search_id=search_id
    )


# ==========================================================
# ADD STUDENT
# ==========================================================

@app.route(
    "/students/add",
    methods=["GET", "POST"]
)
@login_required
def add_student():

    if request.method == "POST":

        student_name = request.form.get(
            "student_name", ""
        )

        roll_no = request.form.get(
            "roll_no", ""
        )

        father_name = request.form.get(
            "father_name", ""
        )

        date_of_birth = request.form.get(
            "date_of_birth", ""
        )

        gender = request.form.get(
            "gender", ""
        )

        class_name = request.form.get(
            "class_name", ""
        )

        section = request.form.get(
            "section", ""
        )

        student_phone = request.form.get(
            "student_phone", ""
        )

        parent_phone = request.form.get(
            "parent_phone", ""
        )

        address = request.form.get(
            "address", ""
        )

        monthly_fee = request.form.get(
            "monthly_fee"
        ) or "0"

        previous_school = request.form.get(
            "previous_school", ""
        )

        previous_coaching = request.form.get(
            "previous_coaching", ""
        )

        try:
            monthly_fee = float(monthly_fee)
        except (ValueError, TypeError):
            monthly_fee = 0.0

        db = get_firestore_db()

        db.collection("students").add({
            "student_name":      student_name,
            "roll_no":           roll_no,
            "father_name":       father_name,
            "date_of_birth":     date_of_birth,
            "gender":            gender,
            "class_name":        class_name,
            "section":           section,
            "student_phone":     student_phone,
            "parent_phone":      parent_phone,
            "address":           address,
            "monthly_fee":       monthly_fee,
            "previous_school":   previous_school,
            "previous_coaching": previous_coaching,
        })

        return redirect(
            url_for("students")
        )

    return render_template(
        "add_student.html"
    )


# ==========================================================
# UPDATE STUDENT
# ==========================================================

@app.route(
    "/students/update/<student_id>",
    methods=["GET", "POST"]
)
@login_required
def update_student(student_id):

    db = get_firestore_db()

    ref = db.collection("students").document(student_id)
    doc = ref.get()

    if not doc.exists:
        return "Student not found", 404

    student = doc_to_dict(doc)

    if request.method == "POST":

        student_name = request.form.get(
            "student_name", ""
        )

        roll_no = request.form.get(
            "roll_no", ""
        )

        father_name = request.form.get(
            "father_name", ""
        )

        date_of_birth = request.form.get(
            "date_of_birth", ""
        )

        gender = request.form.get(
            "gender", ""
        )

        class_name = request.form.get(
            "class_name", ""
        )

        section = request.form.get(
            "section", ""
        )

        student_phone = request.form.get(
            "student_phone", ""
        )

        parent_phone = request.form.get(
            "parent_phone", ""
        )

        address = request.form.get(
            "address", ""
        )

        monthly_fee = request.form.get(
            "monthly_fee"
        ) or "0"

        previous_school = request.form.get(
            "previous_school", ""
        )

        previous_coaching = request.form.get(
            "previous_coaching", ""
        )

        try:
            monthly_fee = float(monthly_fee)
        except (ValueError, TypeError):
            monthly_fee = 0.0

        ref.update({
            "student_name":      student_name,
            "roll_no":           roll_no,
            "father_name":       father_name,
            "date_of_birth":     date_of_birth,
            "gender":            gender,
            "class_name":        class_name,
            "section":           section,
            "student_phone":     student_phone,
            "parent_phone":      parent_phone,
            "address":           address,
            "monthly_fee":       monthly_fee,
            "previous_school":   previous_school,
            "previous_coaching": previous_coaching,
        })

        return redirect(
            url_for("students")
        )

    return render_template(
        "update_student.html",
        student=student
    )


# ==========================================================
# DELETE STUDENT
# ==========================================================

@app.route(
    "/students/delete/<student_id>",
    methods=["POST"]
)
@login_required
def delete_student(student_id):

    db = get_firestore_db()

    # ----------------------------------------------------------
    # Delete all fee records belonging to this student first
    # ----------------------------------------------------------

    payments = (
        db.collection("fee_payments")
        .where("student_id", "==", student_id)
        .get()
    )

    for payment in payments:
        payment.reference.delete()

    # ----------------------------------------------------------
    # Delete the student document
    # ----------------------------------------------------------

    db.collection("students").document(student_id).delete()

    return redirect(
        url_for("students")
    )


# ==========================================================
# INDIVIDUAL CHALLAN
# NEVER CREATE A DUPLICATE RECORD FOR SAME
# STUDENT + FEE MONTH
# ==========================================================

@app.route(
    "/students/generate/<student_id>",
    methods=["GET", "POST"]
)
@login_required
def generate_challan(student_id):

    db = get_firestore_db()

    doc = db.collection("students").document(student_id).get()

    if not doc.exists:
        return "Student not found", 404

    student = doc_to_dict(doc)

    challan_date = date.today()
    due_date = challan_date + timedelta(days=10)
    fee_month = challan_date.strftime("%B %Y")

    if request.method == "POST":

        tuition_fee = request.form.get("tuition_fee") or "0"
        other_fee   = request.form.get("other_fee")   or "0"
        late_fee    = request.form.get("late_fee")    or "0"
        discount    = request.form.get("discount")    or "0"

        try:
            tuition_fee = float(tuition_fee)
        except (ValueError, TypeError):
            tuition_fee = float(student.get("monthly_fee") or 0)

        try:
            other_fee = float(other_fee)
        except (ValueError, TypeError):
            other_fee = 0.0

        try:
            late_fee = float(late_fee)
        except (ValueError, TypeError):
            late_fee = 0.0

        try:
            discount = float(discount)
        except (ValueError, TypeError):
            discount = 0.0

        total_payable = (
            tuition_fee + other_fee + late_fee - discount
        )

        if total_payable < 0:
            total_payable = 0.0

        # ----------------------------------------------------------
        # Check for existing record (same student + same month)
        # ----------------------------------------------------------

        all_student_payments = (
            db.collection("fee_payments")
            .where("student_id", "==", student_id)
            .get()
        )

        existing_doc = None
        for p_doc in all_student_payments:
            if p_doc.to_dict().get("fee_month") == fee_month:
                existing_doc = p_doc
                break

        if existing_doc:

            existing = doc_to_dict(existing_doc)

            if existing["status"] == "PAID":

                # --------------------------------------------------
                # Already paid — show the existing challan only
                # --------------------------------------------------

                return render_template(
                    "generate_challan.html",

                    student=student,

                    challan_date=(
                        date.fromisoformat(
                            existing["challan_date"]
                        ).strftime("%d-%m-%Y")
                    ),

                    due_date=(
                        date.fromisoformat(
                            existing["due_date"]
                        ).strftime("%d-%m-%Y")
                    ),

                    fee_month=fee_month,

                    tuition_fee=existing["tuition_fee"],
                    other_fee=existing["other_fee"],
                    late_fee=existing["late_fee"],
                    discount=existing["discount"],
                    total_payable=existing["total_payable"]
                )

            # ----------------------------------------------------------
            # Existing unpaid/overdue — update the record
            # ----------------------------------------------------------

            existing_doc.reference.update({
                "challan_date":  challan_date.isoformat(),
                "due_date":      due_date.isoformat(),
                "tuition_fee":   tuition_fee,
                "other_fee":     other_fee,
                "late_fee":      late_fee,
                "discount":      discount,
                "total_payable": total_payable,
            })

        else:

            # ----------------------------------------------------------
            # No record exists — create one
            # ----------------------------------------------------------

            db.collection("fee_payments").add({
                "student_id":    student_id,
                "student_name":  student.get("student_name", ""),
                "father_name":   student.get("father_name", ""),
                "roll_no":       student.get("roll_no", ""),
                "class_name":    student.get("class_name", ""),
                "fee_month":     fee_month,
                "challan_date":  challan_date.isoformat(),
                "due_date":      due_date.isoformat(),
                "tuition_fee":   tuition_fee,
                "other_fee":     other_fee,
                "late_fee":      late_fee,
                "discount":      discount,
                "total_payable": total_payable,
                "status":        "UNPAID",
                "payment_date":  None,
                "amount_received": 0.0,
            })

        return render_template(
            "generate_challan.html",

            student=student,

            challan_date=challan_date.strftime("%d-%m-%Y"),

            due_date=due_date.strftime("%d-%m-%Y"),

            fee_month=fee_month,

            tuition_fee=tuition_fee,

            other_fee=other_fee,

            late_fee=late_fee,

            discount=discount,

            total_payable=total_payable
        )

    # GET request — show the challan entry form
    return render_template(
        "challan_form.html",

        student=student,

        challan_date=challan_date.strftime("%d-%m-%Y"),

        due_date=due_date.strftime("%d-%m-%Y"),

        default_date=challan_date.isoformat()
    )


# ==========================================================
# GENERATE ALL CHALLANS
# NEVER DUPLICATE SAME STUDENT + SAME MONTH
# ==========================================================

@app.route(
    "/students/generate-all",
    methods=["GET", "POST"]
)
@login_required
def generate_all_challans():

    db = get_firestore_db()

    challan_date = date.today()
    due_date     = challan_date + timedelta(days=10)
    fee_month    = challan_date.strftime("%B %Y")

    if request.method == "POST":

        fee_date_input = request.form.get("fee_date") or challan_date.isoformat()
        try:
            parsed_date  = date.fromisoformat(fee_date_input)
            challan_date = parsed_date
            fee_month    = parsed_date.strftime("%B %Y")
        except (ValueError, TypeError):
            pass

        due_date_input = request.form.get("due_date") or (challan_date + timedelta(days=10)).isoformat()
        try:
            due_date = date.fromisoformat(due_date_input)
        except (ValueError, TypeError):
            due_date = challan_date + timedelta(days=10)

        try:
            other_fee = float(request.form.get("other_fee") or 0)
        except (ValueError, TypeError):
            other_fee = 0.0

        try:
            annual_fee = float(request.form.get("annual_fee") or 0)
        except (ValueError, TypeError):
            annual_fee = 0.0

        try:
            stationery_fee = float(request.form.get("stationery_fee") or 0)
        except (ValueError, TypeError):
            stationery_fee = 0.0

        try:
            late_fee = float(request.form.get("late_fee") or 0)
        except (ValueError, TypeError):
            late_fee = 0.0

        try:
            discount = float(request.form.get("discount") or 0)
        except (ValueError, TypeError):
            discount = 0.0

        combined_other_fee = other_fee + annual_fee + stationery_fee

        docs = db.collection("students").get()
        student_list = [doc_to_dict(doc) for doc in docs]
        student_list.sort(
            key=lambda s: (
                int(s.get("class_name") or 0),
                s.get("student_name") or ""
            )
        )

        challans = []

        for student in student_list:

            tuition_fee = float(student.get("monthly_fee") or 0)
            total_payable = max(
                tuition_fee + combined_other_fee + late_fee - discount,
                0.0
            )

            # Safe single-field query to avoid index exceptions
            all_student_payments = (
                db.collection("fee_payments")
                .where("student_id", "==", student["id"])
                .get()
            )

            existing = None
            for p_doc in all_student_payments:
                if p_doc.to_dict().get("fee_month") == fee_month:
                    existing = p_doc.to_dict()
                    break

            if not existing:
                db.collection("fee_payments").add({
                    "student_id":      student["id"],
                    "student_name":    student.get("student_name", ""),
                    "father_name":     student.get("father_name", ""),
                    "roll_no":         student.get("roll_no", ""),
                    "class_name":      student.get("class_name", ""),
                    "fee_month":       fee_month,
                    "challan_date":    challan_date.isoformat(),
                    "due_date":        due_date.isoformat(),
                    "tuition_fee":     tuition_fee,
                    "other_fee":       combined_other_fee,
                    "annual_fee":      annual_fee,
                    "stationery_fee":  stationery_fee,
                    "late_fee":        late_fee,
                    "discount":        discount,
                    "total_payable":   total_payable,
                    "status":          "UNPAID",
                    "payment_date":    None,
                    "amount_received": 0.0,
                })

            challans.append({
                "student":        student,
                "challan_date":   challan_date.strftime("%d-%m-%Y"),
                "due_date":       due_date.strftime("%d-%m-%Y"),
                "fee_month":      fee_month,
                "tuition_fee":    tuition_fee,
                "other_fee":      other_fee,
                "annual_fee":     annual_fee,
                "stationery_fee": stationery_fee,
                "late_fee":       late_fee,
                "discount":       discount,
                "total_payable":  total_payable,
            })

        return render_template(
            "all_challans.html",
            challans=challans
        )

    # GET request — show bulk customization options form
    return render_template(
        "bulk_challan_form.html",
        default_date=challan_date.isoformat(),
        due_date=due_date.strftime("%d-%m-%Y")
    )


# ==========================================================
# FEE PAYMENTS
#
# CATEGORIES:
#   ALL | PAID | UNPAID | OVERDUE
# ==========================================================

@app.route("/fee-payments")
@login_required
def fee_payments():

    search_id = request.args.get(
        "student_id", ""
    ).strip()

    selected_status = request.args.get(
        "status", "ALL"
    ).upper().strip()

    valid_statuses = ["ALL", "PAID", "UNPAID", "OVERDUE"]

    if selected_status not in valid_statuses:
        selected_status = "ALL"

    db = get_firestore_db()

    # ----------------------------------------------------------
    # FETCH RECORDS
    # ----------------------------------------------------------

    if search_id:

        docs = (
            db.collection("fee_payments")
            .where("student_id", "==", search_id)
            .get()
        )

    else:

        docs = db.collection("fee_payments").get()

    payments = [doc_to_dict(doc) for doc in docs]

    # ----------------------------------------------------------
    # CALCULATE DISPLAY STATUS
    #
    # DB stores UNPAID/PAID only.
    # If due date has passed and not paid → display as OVERDUE.
    # ----------------------------------------------------------

    today = date.today()

    for payment in payments:

        if payment.get("status") == "PAID":

            payment["display_status"] = "PAID"

        else:

            try:
                due = date.fromisoformat(payment["due_date"])
                payment["display_status"] = (
                    "OVERDUE" if today > due else "UNPAID"
                )
            except (ValueError, TypeError, KeyError):
                payment["display_status"] = "UNPAID"

        # Overwrite status so templates use it consistently
        payment["status"] = payment["display_status"]

    # ----------------------------------------------------------
    # APPLY CATEGORY FILTER
    # ----------------------------------------------------------

    if selected_status != "ALL":
        payments = [
            p for p in payments
            if p["status"] == selected_status
        ]

    # ----------------------------------------------------------
    # SORT — OVERDUE first, UNPAID next, PAID last
    # ----------------------------------------------------------

    status_order = {"OVERDUE": 0, "UNPAID": 1, "PAID": 2}

    payments.sort(
        key=lambda p: (
            status_order.get(p["status"], 3),
            p.get("due_date", ""),
            p.get("student_name", "")
        )
    )

    return render_template(
        "fee_payments.html",

        payments=payments,

        search_id=search_id,

        selected_status=selected_status
    )


# ==========================================================
# MARK PAYMENT AS PAID
# ==========================================================

@app.route(
    "/fee-payments/mark-paid/<payment_id>",
    methods=["POST"]
)
@login_required
def mark_paid(payment_id):

    db = get_firestore_db()

    ref = db.collection("fee_payments").document(payment_id)
    doc = ref.get()

    if not doc.exists:
        return "Payment record not found", 404

    payment = doc.to_dict()

    # ----------------------------------------------------------
    # Prevent double payment
    # ----------------------------------------------------------

    if payment.get("status") == "PAID":
        return redirect(url_for("fee_payments"))

    ref.update({
        "status":          "PAID",
        "payment_date":    date.today().isoformat(),
        "amount_received": float(payment.get("total_payable") or 0),
    })

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# REVERSE PAYMENT / MARK AS UNPAID
# ==========================================================

@app.route(
    "/fee-payments/mark-unpaid/<payment_id>",
    methods=["POST"]
)
@login_required
def mark_unpaid(payment_id):

    db = get_firestore_db()

    ref = db.collection("fee_payments").document(payment_id)
    doc = ref.get()

    if not doc.exists:
        return "Payment record not found", 404

    ref.update({
        "status":          "UNPAID",
        "payment_date":    None,
        "amount_received": 0.0,
    })

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# DELETE FEE RECORD
# ==========================================================

@app.route(
    "/fee-payments/delete/<payment_id>",
    methods=["POST"]
)
@login_required
def delete_fee_payment(payment_id):

    db = get_firestore_db()

    ref = db.collection("fee_payments").document(payment_id)
    doc = ref.get()

    if not doc.exists:
        return "Fee record not found", 404

    ref.delete()

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )