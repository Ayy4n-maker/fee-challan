from flask import Flask, render_template, request, redirect, url_for, session
from datetime import date, timedelta
import os
import uuid
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

def doc_to_dict(doc, default_index=1):
    """Convert a Firestore DocumentSnapshot to a plain dict with clean 3-digit serial display_id."""
    d = doc.to_dict() or {}
    d["id"] = doc.id
    serial = d.get("serial_id")
    if not serial:
        serial = default_index
    try:
        serial = int(serial)
    except (ValueError, TypeError):
        serial = default_index
    d["serial_id"] = serial
    d["display_id"] = "%03d" % serial
    return d


# ==========================================================
# MULTI-TENANT PORTFOLIO & USER AUTHENTICATION HELPERS
# ==========================================================

DEFAULT_PORTFOLIO_ID = "default_portfolio"


def get_current_portfolio_id():
    """Return the active portfolio_id from session (or default)."""
    return session.get("portfolio_id") or DEFAULT_PORTFOLIO_ID


def is_doc_in_portfolio(doc_dict):
    """Check whether a document dict belongs to current tenant's portfolio."""
    pid = get_current_portfolio_id()
    doc_pid = (doc_dict or {}).get("portfolio_id")
    if pid == DEFAULT_PORTFOLIO_ID:
        # Legacy documents without portfolio_id belong to the default admin
        return doc_pid in (None, "", DEFAULT_PORTFOLIO_ID)
    return doc_pid == pid


def get_portfolio_docs(collection_name):
    """
    Fetch all documents strictly belonging to the active portfolio.
    Safe against Firestore missing index exceptions.
    """
    db = get_firestore_db()
    pid = get_current_portfolio_id()

    if pid == DEFAULT_PORTFOLIO_ID:
        all_docs = db.collection(collection_name).get()
        return [
            d for d in all_docs
            if (d.to_dict() or {}).get("portfolio_id") in (None, "", DEFAULT_PORTFOLIO_ID)
        ]
    else:
        return db.collection(collection_name).where("portfolio_id", "==", pid).get()


def get_user_by_credentials(username, password, role):
    """
    Authenticate against Firestore 'users' collection.
    Falls back to environment ADMIN / STAFF defaults so original credentials
    always continue to work seamlessly.
    """
    db = get_firestore_db()
    uname = username.strip().lower()

    try:
        docs = db.collection("users").where("role", "==", role).get()
        for d in docs:
            u = d.to_dict() or {}
            if u.get("username", "").strip().lower() == uname and u.get("password") == password:
                u["id"] = d.id
                return u
    except Exception as e:
        print(f"Firestore user lookup error: {e}")

    # Fallback to default admin/staff credentials (backward compatibility)
    if role == "admin" and uname == ADMIN_USERNAME.strip().lower() and password == ADMIN_PASSWORD:
        return {
            "username": ADMIN_USERNAME,
            "role": "admin",
            "portfolio_id": DEFAULT_PORTFOLIO_ID,
            "school_name": "Irshad Educational Academy"
        }

    if role == "staff" and uname == STAFF_USERNAME.strip().lower() and password == STAFF_PASSWORD:
        return {
            "username": STAFF_USERNAME,
            "role": "staff",
            "portfolio_id": DEFAULT_PORTFOLIO_ID,
            "school_name": "Irshad Educational Academy"
        }

    return None


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

        user = get_user_by_credentials(username, password, "admin")

        if user:
            session.clear()
            session["admin_logged_in"] = True
            session["username"] = user.get("username", username)
            session["portfolio_id"] = user.get("portfolio_id", DEFAULT_PORTFOLIO_ID)
            session["school_name"] = user.get("school_name", "Irshad Educational Academy")

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
    pid = get_current_portfolio_id()

    # ----------------------------------------------------------
    # COUNT STUDENTS IN THIS PORTFOLIO
    # ----------------------------------------------------------

    students_docs = get_portfolio_docs("students")
    total_students = len(students_docs)

    # ----------------------------------------------------------
    # PAYMENT STATS — fetch portfolio payments and aggregate
    # ----------------------------------------------------------

    payments_docs = get_portfolio_docs("fee_payments")

    total_received = 0.0
    total_paid = 0
    total_unpaid = 0
    total_late_fee = 0.0
    total_annual_fee = 0.0
    total_stationery_fee = 0.0
    total_discount = 0.0

    for doc in payments_docs:

        p = doc.to_dict() or {}
        status = p.get("status", "UNPAID")

        if status == "PAID":

            total_received += float(
                p.get("amount_received") or 0
            )

            total_paid += 1

            total_late_fee += float(
                p.get("late_fee") or 0
            )

            total_annual_fee += float(
                p.get("annual_fee") or 0
            )

            total_stationery_fee += float(
                p.get("stationery_fee") or 0
            )

            total_discount += float(
                p.get("discount") or 0
            )

        else:

            total_unpaid += 1

    # ----------------------------------------------------------
    # EXPENSES & PROFIT/LOSS STATS FOR THIS PORTFOLIO
    # ----------------------------------------------------------
    expenses_docs = get_portfolio_docs("expenses")
    recorded_expenses = sum(float((doc.to_dict() or {}).get("amount") or 0) for doc in expenses_docs)

    teachers_docs = get_portfolio_docs("teachers")
    total_teacher_salaries = sum(float((doc.to_dict() or {}).get("salary") or 0) for doc in teachers_docs)

    total_expenses = recorded_expenses + total_teacher_salaries
    net_profit_loss = total_received - total_expenses

    # ----------------------------------------------------------
    # RETRIEVE LINKED STAFF CREDENTIALS FOR THIS PORTFOLIO
    # ----------------------------------------------------------
    staff_username = STAFF_USERNAME
    staff_password = STAFF_PASSWORD

    try:
        staff_docs = (
            db.collection("users")
            .where("portfolio_id", "==", pid)
            .where("role", "==", "staff")
            .get()
        )
        if staff_docs:
            st = staff_docs[0].to_dict() or {}
            staff_username = st.get("username", staff_username)
            staff_password = st.get("password", staff_password)
    except Exception as e:
        print(f"Error fetching staff user credentials: {e}")

    return render_template(
        "admin.html",

        total_students=total_students,

        total_received=total_received,

        total_paid=total_paid,

        total_unpaid=total_unpaid,

        total_late_fee=total_late_fee,

        total_annual_fee=total_annual_fee,

        total_stationery_fee=total_stationery_fee,

        total_discount=total_discount,

        total_expenses=total_expenses,

        net_profit_loss=net_profit_loss,

        current_username=session.get("username", "admin"),

        current_school_name=session.get("school_name", "Irshad Educational Academy"),

        staff_username=staff_username,

        staff_password=staff_password
    )


# ==========================================================
# UPDATE STAFF CREDENTIALS (FROM ADMIN DASHBOARD)
# ==========================================================

@app.route("/admin/update-staff", methods=["POST"])
@admin_required
def update_staff_credentials():

    new_staff_username = request.form.get("staff_username", "").strip()
    new_staff_password = request.form.get("staff_password", "").strip()

    if not new_staff_username or not new_staff_password:
        return redirect(url_for("admin"))

    db = get_firestore_db()
    pid = get_current_portfolio_id()

    try:
        staff_docs = (
            db.collection("users")
            .where("portfolio_id", "==", pid)
            .where("role", "==", "staff")
            .get()
        )

        if staff_docs:
            staff_docs[0].reference.update({
                "username": new_staff_username,
                "password": new_staff_password,
            })
        else:
            db.collection("users").add({
                "username":     new_staff_username,
                "password":     new_staff_password,
                "role":         "staff",
                "portfolio_id": pid,
                "school_name":  session.get("school_name", "Irshad Educational Academy"),
                "created_at":   date.today().isoformat(),
            })
    except Exception as e:
        print(f"Error updating staff credentials: {e}")

    return redirect(url_for("admin"))


# ==========================================================
# REGISTER NEW PORTFOLIO / ADMIN
# ==========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        admin_username = request.form.get("admin_username", "").strip()
        admin_password = request.form.get("admin_password", "").strip()
        school_name    = request.form.get("school_name", "").strip() or "Irshad Educational Academy"
        staff_username = request.form.get("staff_username", "").strip()
        staff_password = request.form.get("staff_password", "").strip()

        form_data = {
            "admin_username": admin_username,
            "school_name":    school_name,
            "staff_username": staff_username,
        }

        if not admin_username or not admin_password:
            return render_template(
                "register.html",
                error="Admin username and password are required.",
                form_data=form_data
            )

        if not staff_username or not staff_password:
            return render_template(
                "register.html",
                error="Staff username and password are required.",
                form_data=form_data
            )

        if admin_username.lower() == staff_username.lower():
            return render_template(
                "register.html",
                error="Admin and Staff usernames cannot be identical.",
                form_data=form_data
            )

        db = get_firestore_db()

        # Check for existing username collisions
        try:
            existing_users = db.collection("users").get()
            taken_usernames = {
                ADMIN_USERNAME.strip().lower(),
                STAFF_USERNAME.strip().lower()
            }
            for u in existing_users:
                u_name = (u.to_dict() or {}).get("username", "").strip().lower()
                if u_name:
                    taken_usernames.add(u_name)

            if admin_username.lower() in taken_usernames:
                return render_template(
                    "register.html",
                    error=f"Admin username '{admin_username}' is already taken. Please pick another.",
                    form_data=form_data
                )

            if staff_username.lower() in taken_usernames:
                return render_template(
                    "register.html",
                    error=f"Staff username '{staff_username}' is already taken. Please pick another.",
                    form_data=form_data
                )
        except Exception as e:
            print(f"Error checking usernames: {e}")

        # Generate unique portfolio ID
        portfolio_id = f"port_{uuid.uuid4().hex[:10]}"

        # Create Admin Account
        db.collection("users").add({
            "username":     admin_username,
            "password":     admin_password,
            "role":         "admin",
            "portfolio_id": portfolio_id,
            "school_name":  school_name,
            "created_at":   date.today().isoformat(),
        })

        # Create Staff Account
        db.collection("users").add({
            "username":     staff_username,
            "password":     staff_password,
            "role":         "staff",
            "portfolio_id": portfolio_id,
            "school_name":  school_name,
            "created_at":   date.today().isoformat(),
        })

        # Automatically log the new admin in
        session.clear()
        session["admin_logged_in"] = True
        session["username"]        = admin_username
        session["portfolio_id"]    = portfolio_id
        session["school_name"]     = school_name

        return redirect(url_for("admin"))

    return render_template("register.html")


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

        user = get_user_by_credentials(username, password, "staff")

        if user:
            session.clear()
            session["staff_logged_in"] = True
            session["username"]        = user.get("username", username)
            session["portfolio_id"]    = user.get("portfolio_id", DEFAULT_PORTFOLIO_ID)
            session["school_name"]     = user.get("school_name", "Irshad Educational Academy")

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
@login_required
def staff():

    total_students = len(
        get_portfolio_docs("students")
    )

    return render_template(
        "index.html",
        total_students=total_students,
        current_username=session.get("username", "staff"),
        current_school_name=session.get("school_name", "Irshad Educational Academy")
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

    docs = get_portfolio_docs("students")

    student_list = [
        doc_to_dict(doc, default_index=idx)
        for idx, doc in enumerate(docs, start=1)
    ]

    # Sort by class (numeric) then by serial_id
    student_list.sort(
        key=lambda s: (
            int(s.get("class_name") or 0),
            int(s.get("serial_id") or 0),
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

    docs = get_portfolio_docs("students")

    all_students = [
        doc_to_dict(doc, default_index=idx)
        for idx, doc in enumerate(docs, start=1)
    ]

    if search_id:
        clean = search_id.strip()
        student_list = [
            s for s in all_students
            if s["id"] == clean
            or s["display_id"] == clean
            or str(s.get("serial_id")) == clean.lstrip("0")
            or clean.lower() in s.get("student_name", "").lower()
            or clean.lower() in s.get("roll_no", "").lower()
        ]
    else:
        student_list = all_students
        student_list.sort(
            key=lambda s: (
                int(s.get("class_name") or 0),
                int(s.get("serial_id") or 0),
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
        pid = get_current_portfolio_id()

        # Calculate next sequential serial_id within this active portfolio
        portfolio_students_docs = get_portfolio_docs("students")
        serials = []
        for s_doc in portfolio_students_docs:
            s_dict = s_doc.to_dict() or {}
            if s_dict.get("serial_id"):
                try:
                    serials.append(int(s_dict["serial_id"]))
                except (ValueError, TypeError):
                    pass

        next_serial = max(serials, default=len(portfolio_students_docs)) + 1

        db.collection("students").add({
            "portfolio_id":      pid,
            "serial_id":         next_serial,
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

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
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

    ref = db.collection("students").document(student_id)
    doc = ref.get()

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Student not found", 404

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

    ref.delete()

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

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
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
                "portfolio_id":    get_current_portfolio_id(),
                "student_id":      student_id,
                "student_name":    student.get("student_name", ""),
                "father_name":     student.get("father_name", ""),
                "roll_no":         student.get("roll_no", ""),
                "class_name":      student.get("class_name", ""),
                "fee_month":       fee_month,
                "challan_date":    challan_date.isoformat(),
                "due_date":        due_date.isoformat(),
                "tuition_fee":     tuition_fee,
                "other_fee":       other_fee,
                "late_fee":        late_fee,
                "discount":        discount,
                "total_payable":   total_payable,
                "status":          "UNPAID",
                "payment_date":    None,
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

        docs = get_portfolio_docs("students")
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
                    "portfolio_id":    get_current_portfolio_id(),
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
    # FETCH RECORDS STRICTLY FOR ACTIVE PORTFOLIO
    # ----------------------------------------------------------

    if search_id:

        docs = (
            db.collection("fee_payments")
            .where("student_id", "==", search_id)
            .get()
        )
        docs = [d for d in docs if is_doc_in_portfolio(d.to_dict())]

    else:

        docs = get_portfolio_docs("fee_payments")

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

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Payment record not found", 404

    payment = doc.to_dict() or {}

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

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
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

    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Fee record not found", 404

    ref.delete()

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# TEACHERS MANAGEMENT
# ==========================================================

@app.route("/teachers")
@login_required
def teachers():
    docs = get_portfolio_docs("teachers")
    teacher_list = [doc_to_dict(doc, default_index=idx) for idx, doc in enumerate(docs, start=1)]
    teacher_list.sort(key=lambda t: int(t.get("serial_id") or 0))
    return render_template("teachers.html", teachers=teacher_list)


@app.route("/teachers/add", methods=["GET", "POST"])
@login_required
def add_teacher():
    if request.method == "POST":
        teacher_name = request.form.get("teacher_name", "")
        phone = request.form.get("phone", "")
        allotted_class = request.form.get("allotted_class", "")
        allotted_subjects = request.form.get("allotted_subjects", "")
        salary = request.form.get("salary") or "0"

        try:
            salary = float(salary)
        except (ValueError, TypeError):
            salary = 0.0

        db = get_firestore_db()
        pid = get_current_portfolio_id()
        docs = get_portfolio_docs("teachers")
        serials = []
        for d in docs:
            d_dict = d.to_dict() or {}
            if d_dict.get("serial_id"):
                try:
                    serials.append(int(d_dict["serial_id"]))
                except (ValueError, TypeError):
                    pass

        next_serial = max(serials, default=len(docs)) + 1

        db.collection("teachers").add({
            "portfolio_id":      pid,
            "serial_id":         next_serial,
            "teacher_name":      teacher_name,
            "phone":             phone,
            "allotted_class":    allotted_class,
            "allotted_subjects": allotted_subjects,
            "salary":            salary,
        })
        return redirect(url_for("teachers"))

    return render_template("add_teacher.html")


@app.route("/teachers/update/<teacher_id>", methods=["GET", "POST"])
@login_required
def update_teacher(teacher_id):
    db = get_firestore_db()
    ref = db.collection("teachers").document(teacher_id)
    doc = ref.get()
    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Teacher not found", 404

    teacher = doc_to_dict(doc)

    if request.method == "POST":
        teacher_name = request.form.get("teacher_name", "")
        phone = request.form.get("phone", "")
        allotted_class = request.form.get("allotted_class", "")
        allotted_subjects = request.form.get("allotted_subjects", "")
        salary = request.form.get("salary") or "0"

        try:
            salary = float(salary)
        except (ValueError, TypeError):
            salary = 0.0

        ref.update({
            "teacher_name":      teacher_name,
            "phone":             phone,
            "allotted_class":    allotted_class,
            "allotted_subjects": allotted_subjects,
            "salary":            salary,
        })
        return redirect(url_for("teachers"))

    return render_template("update_teacher.html", teacher=teacher)


@app.route("/teachers/delete/<teacher_id>", methods=["POST"])
@login_required
def delete_teacher(teacher_id):
    db = get_firestore_db()
    ref = db.collection("teachers").document(teacher_id)
    doc = ref.get()
    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Teacher not found", 404
    ref.delete()
    return redirect(url_for("teachers"))


# ==========================================================
# EXPENSES MANAGEMENT
# ==========================================================

@app.route("/expenses")
@login_required
def expenses():
    docs = get_portfolio_docs("expenses")
    expense_list = [doc_to_dict(doc, default_index=idx) for idx, doc in enumerate(docs, start=1)]
    expense_list.sort(key=lambda e: e.get("expense_date", ""), reverse=True)

    total_expenses_sum = sum(float(e.get("amount") or 0) for e in expense_list)

    return render_template("expenses.html", expenses=expense_list, total_expenses_sum=total_expenses_sum)


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        category = request.form.get("category", "")
        description = request.form.get("description", "")
        amount = request.form.get("amount") or "0"
        expense_date = request.form.get("expense_date") or date.today().isoformat()

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0.0

        db = get_firestore_db()
        pid = get_current_portfolio_id()
        docs = get_portfolio_docs("expenses")
        serials = []
        for d in docs:
            d_dict = d.to_dict() or {}
            if d_dict.get("serial_id"):
                try:
                    serials.append(int(d_dict["serial_id"]))
                except (ValueError, TypeError):
                    pass

        next_serial = max(serials, default=len(docs)) + 1

        db.collection("expenses").add({
            "portfolio_id": pid,
            "serial_id":    next_serial,
            "category":     category,
            "description":  description,
            "amount":       amount,
            "expense_date": expense_date,
        })
        return redirect(url_for("expenses"))

    return render_template("add_expense.html", default_date=date.today().isoformat())


@app.route("/expenses/delete/<expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    db = get_firestore_db()
    ref = db.collection("expenses").document(expense_id)
    doc = ref.get()
    if not doc.exists or not is_doc_in_portfolio(doc.to_dict()):
        return "Expense record not found", 404
    ref.delete()
    return redirect(url_for("expenses"))


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )