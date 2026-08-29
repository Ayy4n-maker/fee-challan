from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "fee_system.db")


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

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

    conn.commit()
    conn.close()


@app.route("/")
def home():

    conn = get_db()

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        total_students=total_students
    )


@app.route("/students")
def students():
    conn = get_db()

    student_list = conn.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=student_list
    )


@app.route("/students/add", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":

        student_name = request.form.get("student_name", "")
        roll_no = request.form.get("roll_no", "")
        father_name = request.form.get("father_name", "")
        date_of_birth = request.form.get("date_of_birth", "")
        gender = request.form.get("gender", "")
        class_name = request.form.get("class_name", "")
        section = request.form.get("section", "")
        student_phone = request.form.get("student_phone", "")
        parent_phone = request.form.get("parent_phone", "")
        address = request.form.get("address", "")
        monthly_fee = request.form.get("monthly_fee") or "0"
        previous_school = request.form.get("previous_school", "")
        previous_coaching = request.form.get("previous_coaching", "")

        try:
            monthly_fee = float(monthly_fee)
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        return redirect(url_for("students"))

    return render_template("add_student.html")


@app.route("/students/update/<int:student_id>", methods=["GET", "POST"])
def update_student(student_id):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (student_id,)).fetchone()

    if student is None:
        conn.close()
        return "Student not found", 404

    if request.method == "POST":

        student_name = request.form.get("student_name", "")
        roll_no = request.form.get("roll_no", "")
        father_name = request.form.get("father_name", "")
        date_of_birth = request.form.get("date_of_birth", "")
        gender = request.form.get("gender", "")
        class_name = request.form.get("class_name", "")
        section = request.form.get("section", "")
        student_phone = request.form.get("student_phone", "")
        parent_phone = request.form.get("parent_phone", "")
        address = request.form.get("address", "")
        monthly_fee = request.form.get("monthly_fee") or "0"
        previous_school = request.form.get("previous_school", "")
        previous_coaching = request.form.get("previous_coaching", "")

        try:
            monthly_fee = float(monthly_fee)
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

        return redirect(url_for("students"))

    conn.close()

    return render_template(
        "update_student.html",
        student=student
    )


@app.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):

    conn = get_db()

    conn.execute("""
        DELETE FROM students
        WHERE id = ?
    """, (student_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("students"))


@app.route("/students/generate/<int:student_id>", methods=["GET", "POST"])
def generate_challan(student_id):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (student_id,)).fetchone()

    conn.close()

    if student is None:
        return "Student not found", 404

    today = date.today().isoformat()

    if request.method == "POST":

        fee_month = request.form.get("fee_month") or today

        tuition_fee = request.form.get("tuition_fee") or "0"
        other_fee = request.form.get("other_fee") or "0"
        late_fee = request.form.get("late_fee") or "0"
        discount = request.form.get("discount") or "0"

        try:
            tuition_fee = float(tuition_fee)
        except:
            tuition_fee = float(student["monthly_fee"] or 0)

        try:
            other_fee = float(other_fee)
        except:
            other_fee = 0

        try:
            late_fee = float(late_fee)
        except:
            late_fee = 0

        try:
            discount = float(discount)
        except:
            discount = 0

        total_payable = tuition_fee + other_fee + late_fee - discount

        if total_payable < 0:
            total_payable = 0

        return render_template(
            "generate_challan.html",
            student=student,
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
        default_date=today
    )


@app.route("/students/generate-all", methods=["GET", "POST"])
def generate_all_challans():

    conn = get_db()

    student_list = conn.execute("""
        SELECT *
        FROM students
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    today = date.today().isoformat()

    if request.method == "POST":
        fee_date = request.form.get("fee_date") or today
    else:
        fee_date = today

    challans = []

    for student in student_list:

        tuition_fee = float(student["monthly_fee"] or 0)

        other_fee = 0
        late_fee = 0
        discount = 0

        total_payable = tuition_fee + other_fee + late_fee - discount

        if total_payable < 0:
            total_payable = 0

        challans.append({
            "student": student,
            "fee_date": fee_date,
            "tuition_fee": tuition_fee,
            "other_fee": other_fee,
            "late_fee": late_fee,
            "discount": discount,
            "total_payable": total_payable
        })

    return render_template(
        "all_challans.html",
        challans=challans,
        default_date=today
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)