from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import date, timedelta
import os
from functools import wraps


app = Flask(__name__)

# ==========================================================
# SECRET KEY
# ==========================================================

app.secret_key = "IESC_FEE_SYSTEM_SECRET_KEY_2026"


# ==========================================================
# DATABASE
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "fee_system.db")


# ==========================================================
# LOGIN DETAILS
# CHANGE THESE LATER IF YOU WANT
# ==========================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

STAFF_USERNAME = "staff"
STAFF_PASSWORD = "staff123"


# ==========================================================
# DATABASE CONNECTION
# ==========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE,
        timeout=10
    )

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================

def init_db():

    conn = get_db()

    # ------------------------------------------------------
    # STUDENTS TABLE
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_name TEXT NOT NULL,

            roll_no TEXT NOT NULL,

            father_name TEXT NOT NULL,

            date_of_birth TEXT,

            gender TEXT,

            class_name TEXT NOT NULL,

            section TEXT,

            student_phone TEXT,

            parent_phone TEXT NOT NULL,

            address TEXT,

            monthly_fee REAL NOT NULL,

            fee_month TEXT,

            previous_school TEXT,

            previous_coaching TEXT
        )
    """)

    # ------------------------------------------------------
    # FEE PAYMENTS TABLE
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fee_payments (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER NOT NULL,

            fee_month TEXT NOT NULL,

            challan_date TEXT NOT NULL,

            due_date TEXT NOT NULL,

            tuition_fee REAL DEFAULT 0,

            other_fee REAL DEFAULT 0,

            late_fee REAL DEFAULT 0,

            discount REAL DEFAULT 0,

            total_payable REAL DEFAULT 0,

            status TEXT DEFAULT 'UNPAID',

            payment_date TEXT,

            amount_received REAL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(student_id)
                REFERENCES students(id)
        )
    """)

    conn.commit()

    conn.close()


# ==========================================================
# LOGIN PROTECTION
# ==========================================================

def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if session.get("admin_logged_in") != True:

            return redirect(
                url_for("admin_login")
            )

        return function(*args, **kwargs)

    return decorated_function


def staff_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if session.get("staff_logged_in") != True:

            return redirect(
                url_for("staff_login")
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
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
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

    conn = get_db()

    total_students = conn.execute("""
        SELECT COUNT(*)
        FROM students
    """).fetchone()[0]

    total_received = conn.execute("""
        SELECT COALESCE(
            SUM(amount_received),
            0
        )
        FROM fee_payments
        WHERE status = 'PAID'
    """).fetchone()[0]

    total_paid = conn.execute("""
        SELECT COUNT(*)
        FROM fee_payments
        WHERE status = 'PAID'
    """).fetchone()[0]

    total_unpaid = conn.execute("""
        SELECT COUNT(*)
        FROM fee_payments
        WHERE status != 'PAID'
    """).fetchone()[0]

    total_late_fee = conn.execute("""
        SELECT COALESCE(
            SUM(late_fee),
            0
        )
        FROM fee_payments
        WHERE status = 'PAID'
    """).fetchone()[0]

    conn.close()

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
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
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

    conn = get_db()

    total_students = conn.execute("""
        SELECT COUNT(*)
        FROM students
    """).fetchone()[0]

    conn.close()

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
@staff_required
def students():

    conn = get_db()

    student_list = conn.execute("""
        SELECT *
        FROM students
        ORDER BY
            CAST(class_name AS INTEGER) ASC,
            student_name ASC
    """).fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=student_list
    )


# ==========================================================
# GENERATE CHALLAN LIST
# STUDENT ID SEARCH
# ==========================================================

@app.route("/generate-challan")
@staff_required
def generate_challan_list():

    search_id = request.args.get(
        "student_id",
        ""
    ).strip()

    conn = get_db()

    if search_id:

        try:

            student_id = int(search_id)

            student_list = conn.execute("""
                SELECT *
                FROM students
                WHERE id = ?
            """, (
                student_id,
            )).fetchall()

        except ValueError:

            student_list = []

    else:

        student_list = conn.execute("""
            SELECT *
            FROM students
            ORDER BY
                CAST(class_name AS INTEGER) ASC,
                student_name ASC
        """).fetchall()

    conn.close()

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
@staff_required
def add_student():

    if request.method == "POST":

        student_name = request.form.get(
            "student_name",
            ""
        )

        roll_no = request.form.get(
            "roll_no",
            ""
        )

        father_name = request.form.get(
            "father_name",
            ""
        )

        date_of_birth = request.form.get(
            "date_of_birth",
            ""
        )

        gender = request.form.get(
            "gender",
            ""
        )

        class_name = request.form.get(
            "class_name",
            ""
        )

        section = request.form.get(
            "section",
            ""
        )

        student_phone = request.form.get(
            "student_phone",
            ""
        )

        parent_phone = request.form.get(
            "parent_phone",
            ""
        )

        address = request.form.get(
            "address",
            ""
        )

        monthly_fee = request.form.get(
            "monthly_fee"
        ) or "0"

        previous_school = request.form.get(
            "previous_school",
            ""
        )

        previous_coaching = request.form.get(
            "previous_coaching",
            ""
        )

        try:

            monthly_fee = float(
                monthly_fee
            )

        except:

            monthly_fee = 0

        conn = get_db()

        conn.execute("""
            INSERT INTO students (
                student_name,
                roll_no,
                father_name,
                date_of_birth,
                gender,
                class_name,
                section,
                student_phone,
                parent_phone,
                address,
                monthly_fee,
                fee_month,
                previous_school,
                previous_coaching
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
        """, (
            student_name,
            roll_no,
            father_name,
            date_of_birth,
            gender,
            class_name,
            section,
            student_phone,
            parent_phone,
            address,
            monthly_fee,
            None,
            previous_school,
            previous_coaching
        ))

        conn.commit()

        conn.close()

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
    "/students/update/<int:student_id>",
    methods=["GET", "POST"]
)
@staff_required
def update_student(student_id):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        student_id,
    )).fetchone()

    if student is None:

        conn.close()

        return "Student not found", 404

    if request.method == "POST":

        student_name = request.form.get(
            "student_name",
            ""
        )

        roll_no = request.form.get(
            "roll_no",
            ""
        )

        father_name = request.form.get(
            "father_name",
            ""
        )

        date_of_birth = request.form.get(
            "date_of_birth",
            ""
        )

        gender = request.form.get(
            "gender",
            ""
        )

        class_name = request.form.get(
            "class_name",
            ""
        )

        section = request.form.get(
            "section",
            ""
        )

        student_phone = request.form.get(
            "student_phone",
            ""
        )

        parent_phone = request.form.get(
            "parent_phone",
            ""
        )

        address = request.form.get(
            "address",
            ""
        )

        monthly_fee = request.form.get(
            "monthly_fee"
        ) or "0"

        previous_school = request.form.get(
            "previous_school",
            ""
        )

        previous_coaching = request.form.get(
            "previous_coaching",
            ""
        )

        try:

            monthly_fee = float(
                monthly_fee
            )

        except:

            monthly_fee = 0

        conn.execute("""
            UPDATE students

            SET
                student_name = ?,
                roll_no = ?,
                father_name = ?,
                date_of_birth = ?,
                gender = ?,
                class_name = ?,
                section = ?,
                student_phone = ?,
                parent_phone = ?,
                address = ?,
                monthly_fee = ?,
                previous_school = ?,
                previous_coaching = ?

            WHERE id = ?
        """, (
            student_name,
            roll_no,
            father_name,
            date_of_birth,
            gender,
            class_name,
            section,
            student_phone,
            parent_phone,
            address,
            monthly_fee,
            previous_school,
            previous_coaching,
            student_id
        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for("students")
        )

    conn.close()

    return render_template(
        "update_student.html",
        student=student
    )


# ==========================================================
# DELETE STUDENT
# ==========================================================

@app.route(
    "/students/delete/<int:student_id>",
    methods=["POST"]
)
@staff_required
def delete_student(student_id):

    conn = get_db()

    # Delete fee records belonging to student first
    conn.execute("""
        DELETE FROM fee_payments
        WHERE student_id = ?
    """, (
        student_id,
    ))

    conn.execute("""
        DELETE FROM students
        WHERE id = ?
    """, (
        student_id,
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("students")
    )


# ==========================================================
# INDIVIDUAL CHALLAN
# IMPORTANT:
# NEVER CREATE A DUPLICATE RECORD FOR SAME
# STUDENT + FEE MONTH
# ==========================================================

@app.route(
    "/students/generate/<int:student_id>",
    methods=["GET", "POST"]
)
@staff_required
def generate_challan(student_id):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (
        student_id,
    )).fetchone()

    conn.close()

    if student is None:

        return "Student not found", 404

    challan_date = date.today()

    due_date = challan_date + timedelta(
        days=10
    )

    fee_month = challan_date.strftime(
        "%B %Y"
    )

    if request.method == "POST":

        tuition_fee = request.form.get(
            "tuition_fee"
        ) or "0"

        other_fee = request.form.get(
            "other_fee"
        ) or "0"

        late_fee = request.form.get(
            "late_fee"
        ) or "0"

        discount = request.form.get(
            "discount"
        ) or "0"

        try:

            tuition_fee = float(
                tuition_fee
            )

        except:

            tuition_fee = float(
                student["monthly_fee"] or 0
            )

        try:

            other_fee = float(
                other_fee
            )

        except:

            other_fee = 0

        try:

            late_fee = float(
                late_fee
            )

        except:

            late_fee = 0

        try:

            discount = float(
                discount
            )

        except:

            discount = 0

        total_payable = (
            tuition_fee
            + other_fee
            + late_fee
            - discount
        )

        if total_payable < 0:

            total_payable = 0

        conn = get_db()

        # --------------------------------------------------
        # FIXED DUPLICATE LOGIC
        #
        # Search for ANY record for this student/month.
        # We do NOT use status != PAID.
        # --------------------------------------------------

        existing = conn.execute("""
            SELECT *
            FROM fee_payments

            WHERE student_id = ?
              AND fee_month = ?

            ORDER BY id DESC

            LIMIT 1
        """, (
            student_id,
            fee_month
        )).fetchone()

        if existing:

            # ----------------------------------------------
            # If already PAID, don't create another record.
            # Keep the payment record intact.
            # ----------------------------------------------

            if existing["status"] == "PAID":

                challan_date_display = existing["challan_date"]
                due_date_display = existing["due_date"]

                existing_tuition = existing["tuition_fee"]
                existing_other = existing["other_fee"]
                existing_late = existing["late_fee"]
                existing_discount = existing["discount"]
                existing_total = existing["total_payable"]

                conn.close()

                return render_template(
                    "generate_challan.html",

                    student=student,

                    challan_date=(
                        date.fromisoformat(
                            challan_date_display
                        ).strftime("%d-%m-%Y")
                    ),

                    due_date=(
                        date.fromisoformat(
                            due_date_display
                        ).strftime("%d-%m-%Y")
                    ),

                    fee_month=fee_month,

                    tuition_fee=existing_tuition,

                    other_fee=existing_other,

                    late_fee=existing_late,

                    discount=existing_discount,

                    total_payable=existing_total
                )

            # ----------------------------------------------
            # Existing unpaid/overdue record
            # Update the same record.
            # ----------------------------------------------

            conn.execute("""
                UPDATE fee_payments

                SET
                    challan_date = ?,
                    due_date = ?,
                    tuition_fee = ?,
                    other_fee = ?,
                    late_fee = ?,
                    discount = ?,
                    total_payable = ?

                WHERE id = ?
            """, (
                challan_date.isoformat(),
                due_date.isoformat(),
                tuition_fee,
                other_fee,
                late_fee,
                discount,
                total_payable,
                existing["id"]
            ))

        else:

            # ----------------------------------------------
            # No record exists, so create one.
            # ----------------------------------------------

            conn.execute("""
                INSERT INTO fee_payments (
                    student_id,
                    fee_month,
                    challan_date,
                    due_date,
                    tuition_fee,
                    other_fee,
                    late_fee,
                    discount,
                    total_payable,
                    status
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UNPAID'
                )
            """, (
                student_id,
                fee_month,
                challan_date.isoformat(),
                due_date.isoformat(),
                tuition_fee,
                other_fee,
                late_fee,
                discount,
                total_payable
            ))

        conn.commit()

        conn.close()

        return render_template(
            "generate_challan.html",

            student=student,

            challan_date=
                challan_date.strftime(
                    "%d-%m-%Y"
                ),

            due_date=
                due_date.strftime(
                    "%d-%m-%Y"
                ),

            fee_month=fee_month,

            tuition_fee=tuition_fee,

            other_fee=other_fee,

            late_fee=late_fee,

            discount=discount,

            total_payable=total_payable
        )

    return render_template(
        "challan_form.html",

        student=student,

        challan_date=
            challan_date.strftime(
                "%d-%m-%Y"
            ),

        due_date=
            due_date.strftime(
                "%d-%m-%Y"
            )
    )


# ==========================================================
# GENERATE ALL CHALLANS
# FIXED:
# NEVER DUPLICATE SAME STUDENT + SAME MONTH
# ==========================================================

@app.route(
    "/students/generate-all",
    methods=["GET", "POST"]
)
@staff_required
def generate_all_challans():

    conn = get_db()

    student_list = conn.execute("""
        SELECT *
        FROM students
        ORDER BY
            CAST(class_name AS INTEGER) ASC,
            student_name ASC
    """).fetchall()

    challan_date = date.today()

    due_date = challan_date + timedelta(
        days=10
    )

    fee_month = challan_date.strftime(
        "%B %Y"
    )

    challans = []

    for student in student_list:

        tuition_fee = float(
            student["monthly_fee"] or 0
        )

        other_fee = 0

        late_fee = 0

        discount = 0

        total_payable = (
            tuition_fee
            + other_fee
            + late_fee
            - discount
        )

        if total_payable < 0:

            total_payable = 0

        # --------------------------------------------------
        # IMPORTANT FIX
        #
        # Search for ANY existing record.
        # Previously the code searched only for records
        # where status != PAID.
        #
        # Therefore a PAID record was ignored and a new
        # duplicate was created.
        # --------------------------------------------------

        existing = conn.execute("""
            SELECT *
            FROM fee_payments

            WHERE student_id = ?
              AND fee_month = ?

            ORDER BY id DESC

            LIMIT 1
        """, (
            student["id"],
            fee_month
        )).fetchone()

        if existing is None:

            # ----------------------------------------------
            # Create record only if none exists
            # ----------------------------------------------

            conn.execute("""
                INSERT INTO fee_payments (
                    student_id,
                    fee_month,
                    challan_date,
                    due_date,
                    tuition_fee,
                    other_fee,
                    late_fee,
                    discount,
                    total_payable,
                    status
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UNPAID'
                )
            """, (
                student["id"],
                fee_month,
                challan_date.isoformat(),
                due_date.isoformat(),
                tuition_fee,
                other_fee,
                late_fee,
                discount,
                total_payable
            ))

        else:

            # ----------------------------------------------
            # DO NOTHING if record already exists.
            #
            # This is especially important when PAID.
            # We must never create another record.
            # ----------------------------------------------

            pass

        challans.append({

            "student": student,

            "challan_date":
                challan_date.strftime(
                    "%d-%m-%Y"
                ),

            "due_date":
                due_date.strftime(
                    "%d-%m-%Y"
                ),

            "fee_month":
                fee_month,

            "tuition_fee":
                tuition_fee,

            "other_fee":
                other_fee,

            "late_fee":
                late_fee,

            "discount":
                discount,

            "total_payable":
                total_payable
        })

    conn.commit()

    conn.close()

    return render_template(
        "all_challans.html",
        challans=challans
    )


# ==========================================================
# FEE PAYMENTS
#
# CATEGORIES:
# ALL
# PAID
# UNPAID
# OVERDUE
# ==========================================================

@app.route("/fee-payments")
@staff_required
def fee_payments():

    search_id = request.args.get(
        "student_id",
        ""
    ).strip()

    selected_status = request.args.get(
        "status",
        "ALL"
    ).upper().strip()

    # Make sure only valid categories are accepted

    valid_statuses = [
        "ALL",
        "PAID",
        "UNPAID",
        "OVERDUE"
    ]

    if selected_status not in valid_statuses:

        selected_status = "ALL"

    conn = get_db()

    # ------------------------------------------------------
    # GET RECORDS
    # ------------------------------------------------------

    if search_id:

        try:

            student_id = int(
                search_id
            )

            payments = conn.execute("""
                SELECT
                    fee_payments.*,

                    students.student_name,
                    students.father_name,
                    students.roll_no,
                    students.class_name

                FROM fee_payments

                JOIN students

                ON students.id =
                   fee_payments.student_id

                WHERE students.id = ?

                ORDER BY
                    fee_payments.id DESC
            """, (
                student_id,
            )).fetchall()

        except ValueError:

            payments = []

    else:

        payments = conn.execute("""
            SELECT
                fee_payments.*,

                students.student_name,
                students.father_name,
                students.roll_no,
                students.class_name

            FROM fee_payments

            JOIN students

            ON students.id =
               fee_payments.student_id

            ORDER BY
                fee_payments.due_date ASC,
                students.student_name ASC
        """).fetchall()

    conn.close()

    # ------------------------------------------------------
    # CALCULATE REAL STATUS
    #
    # A database record remains UNPAID internally.
    # If due date has passed, we display it as OVERDUE.
    # ------------------------------------------------------

    today = date.today()

    payment_list = []

    for payment in payments:

        payment = dict(payment)

        if payment["status"] == "PAID":

            display_status = "PAID"

        else:

            try:

                due = date.fromisoformat(
                    payment["due_date"]
                )

                if today > due:

                    display_status = "OVERDUE"

                else:

                    display_status = "UNPAID"

            except:

                display_status = "UNPAID"

        payment["display_status"] = display_status

        # Keep status compatible with your existing template

        payment["status"] = display_status

        payment_list.append(
            payment
        )

    # ------------------------------------------------------
    # APPLY CATEGORY FILTER
    # ------------------------------------------------------

    if selected_status != "ALL":

        payment_list = [
            payment
            for payment in payment_list
            if payment["status"] == selected_status
        ]

    # ------------------------------------------------------
    # ORDER BY CATEGORY
    #
    # PAID at bottom
    # OVERDUE before UNPAID
    # ------------------------------------------------------

    def payment_sort(payment):

        status_order = {
            "OVERDUE": 0,
            "UNPAID": 1,
            "PAID": 2
        }

        return (
            status_order.get(
                payment["status"],
                3
            ),

            payment["due_date"],

            payment["student_name"]
        )

    payment_list.sort(
        key=payment_sort
    )

    return render_template(
        "fee_payments.html",

        payments=payment_list,

        search_id=search_id,

        selected_status=selected_status
    )


# ==========================================================
# MARK PAYMENT AS PAID
# ==========================================================

@app.route(
    "/fee-payments/mark-paid/<int:payment_id>",
    methods=["POST"]
)
@staff_required
def mark_paid(payment_id):

    conn = get_db()

    payment = conn.execute("""
        SELECT *
        FROM fee_payments
        WHERE id = ?
    """, (
        payment_id,
    )).fetchone()

    if payment is None:

        conn.close()

        return "Payment record not found", 404

    # ------------------------------------------------------
    # PREVENT DOUBLE PAYMENT
    # ------------------------------------------------------

    if payment["status"] == "PAID":

        conn.close()

        return redirect(
            url_for("fee_payments")
        )

    payment_date = date.today().isoformat()

    amount_received = float(
        payment["total_payable"] or 0
    )

    conn.execute("""
        UPDATE fee_payments

        SET
            status = 'PAID',
            payment_date = ?,
            amount_received = ?

        WHERE id = ?
    """, (
        payment_date,
        amount_received,
        payment_id
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# REVERSE PAYMENT / MARK AS UNPAID
# ==========================================================

@app.route(
    "/fee-payments/mark-unpaid/<int:payment_id>",
    methods=["POST"]
)
@staff_required
def mark_unpaid(payment_id):

    conn = get_db()

    payment = conn.execute("""
        SELECT *
        FROM fee_payments
        WHERE id = ?
    """, (
        payment_id,
    )).fetchone()

    if payment is None:

        conn.close()

        return "Payment record not found", 404

    conn.execute("""
        UPDATE fee_payments

        SET
            status = 'UNPAID',
            payment_date = NULL,
            amount_received = 0

        WHERE id = ?
    """, (
        payment_id,
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# DELETE FEE RECORD
# ==========================================================

@app.route(
    "/fee-payments/delete/<int:payment_id>",
    methods=["POST"]
)
@staff_required
def delete_fee_payment(payment_id):

    conn = get_db()

    payment = conn.execute("""
        SELECT *
        FROM fee_payments
        WHERE id = ?
    """, (
        payment_id,
    )).fetchone()

    if payment is None:

        conn.close()

        return "Fee record not found", 404

    conn.execute("""
        DELETE FROM fee_payments
        WHERE id = ?
    """, (
        payment_id,
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("fee_payments")
    )


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )