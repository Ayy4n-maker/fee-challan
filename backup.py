from io import BytesIO
from datetime import date, datetime
import calendar

from flask import render_template, request, redirect, url_for, session, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app import app, get_portfolio_docs


def _admin_ok():
    return session.get("admin_logged_in") is True


def _value(v):
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_value(x)}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return ", ".join(_value(x) for x in v)
    return v


def _rows(collection):
    result = []
    for doc in get_portfolio_docs(collection):
        row = doc.to_dict() or {}
        row["document_id"] = doc.id
        result.append(row)
    return result


def _money(row, *names):
    for name in names:
        try:
            return float(row.get(name) or 0)
        except (TypeError, ValueError):
            pass
    return 0.0


def _make_sheet(wb, title, rows):
    ws = wb.create_sheet(title[:31])
    if not rows:
        ws.append(["No records found"])
        return ws
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    ws.append(keys)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E3A8A")
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append([_value(row.get(key)) for key in keys])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        length = max(len(str(c.value or "")) for c in col[:80])
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, 12), 35)
    return ws


def _date_text(row):
    for key in ("payment_date", "paid_at", "date", "expense_date", "created_at", "challan_date", "issue_date"):
        if row.get(key):
            return str(_value(row.get(key)))
    return "Unknown"


def _date_match(row, month, year):
    for key in ("payment_date", "paid_at", "date", "expense_date", "created_at", "challan_date", "issue_date"):
        value = row.get(key)
        if not value:
            continue
        text = str(value)
        if f"{year}-{month:02d}" in text or f"{month:02d}-{year}" in text:
            return True
    fee_month = str(row.get("fee_month") or "").lower()
    return calendar.month_name[month].lower() in fee_month or calendar.month_abbr[month].lower() in fee_month


def _build(month=None, year=None):
    monthly = month is not None and year is not None
    students = _rows("students")
    teachers = _rows("teachers")
    payments = _rows("fee_payments")
    expenses = _rows("expenses")
    challans = _rows("challans")

    report_payments = payments
    report_expenses = expenses
    report_challans = challans
    if monthly:
        report_payments = [p for p in payments if _date_match(p, month, year)]
        report_expenses = [e for e in expenses if _date_match(e, month, year)]
        report_challans = [c for c in challans if _date_match(c, month, year)]

    paid_payments = [p for p in report_payments if str(p.get("status", "")).upper() == "PAID"]

    revenue = sum(_money(p, "amount_received", "amount_paid", "total_payable", "total_amount") for p in paid_payments)
    tuition = sum(_money(p, "monthly_fee", "tuition_fee", "fee_amount") for p in paid_payments)
    late = sum(_money(p, "late_fee", "late_charges") for p in paid_payments)
    annual = sum(_money(p, "annual_fee", "annual_charges") for p in paid_payments)
    stationery = sum(_money(p, "stationery_fee", "exam_fee", "stationery_exam_fee") for p in paid_payments)
    admission = sum(_money(p, "admission_fee", "additional_fee") for p in paid_payments)
    other = sum(_money(p, "other_fee", "other_charges") for p in paid_payments)
    discount = sum(_money(p, "discount") for p in paid_payments)
    expenses_total = sum(_money(e, "amount", "expense_amount") for e in report_expenses)
    salaries = sum(_money(t, "salary") for t in teachers)
    total_expenses = expenses_total + salaries

    wb = Workbook()
    wb.remove(wb.active)
    summary = wb.create_sheet("Summary")
    summary.append(["IESC BACKUP", ""])
    summary.append(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    summary.append(["School", session.get("school_name", "Irshad Educational Academy")])
    summary.append(["Period", f"{calendar.month_name[month]} {year}" if monthly else "Complete history to date"])
    summary.append([])
    summary.append(["Financial Item", "Amount (Rs.)"])
    for label, amount in [
        ("Total Revenue", revenue),
        ("Tuition / Monthly Fees", tuition),
        ("Admission / Additional Fees", admission),
        ("Annual Charges", annual),
        ("Stationery / Exam Fees", stationery),
        ("Late Charges", late),
        ("Other Charges", other),
        ("Discounts Given", discount),
        ("Recorded Expenses", expenses_total),
        ("Teacher Salaries", salaries),
        ("Total Expenses", total_expenses),
        ("Profit / Loss", revenue - total_expenses),
    ]:
        summary.append([label, amount])
    summary.append([])
    summary.append(["Record Type", "Count"])
    for label, count in [("Students", len(students)), ("Teachers", len(teachers)), ("Fee Payment Records", len(report_payments)), ("Paid Payments", len(paid_payments)), ("Expenses", len(report_expenses)), ("Challans", len(report_challans))]:
        summary.append([label, count])
    for cell in summary[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E3A8A")
    summary.column_dimensions["A"].width = 36
    summary.column_dimensions["B"].width = 24

    _make_sheet(wb, "Students", students)
    _make_sheet(wb, "Teachers", teachers)
    _make_sheet(wb, "Fee Payments", report_payments)
    _make_sheet(wb, "Challans", report_challans)
    _make_sheet(wb, "Expenses", report_expenses)
    _make_sheet(wb, "Revenue Sources", [
        {"source": "Tuition / Monthly Fees", "amount": tuition},
        {"source": "Admission / Additional Fees", "amount": admission},
        {"source": "Annual Charges", "amount": annual},
        {"source": "Stationery / Exam Fees", "amount": stationery},
        {"source": "Late Charges", "amount": late},
        {"source": "Other Charges", "amount": other},
        {"source": "Discounts Given", "amount": discount},
        {"source": "Total Revenue Received", "amount": revenue},
    ])
    _make_sheet(wb, "Monthly Revenue", [{
        "period": f"{calendar.month_name[month]} {year}" if monthly else "Complete history",
        "revenue": revenue,
        "paid_payments": len(paid_payments),
        "tuition": tuition,
        "admission": admission,
        "annual": annual,
        "stationery_exam": stationery,
        "late": late,
        "other": other,
        "discounts": discount,
    }])
    _make_sheet(wb, "Profit & Loss", [
        {"item": "Revenue", "amount": revenue},
        {"item": "Recorded Expenses", "amount": expenses_total},
        {"item": "Teacher Salaries", "amount": salaries},
        {"item": "Total Expenses", "amount": total_expenses},
        {"item": "Profit / Loss", "amount": revenue - total_expenses},
    ])
    return wb


@app.route("/admin/backup")
def backup_page():
    if not _admin_ok():
        return redirect(url_for("admin_login"))
    today = date.today()
    return render_template("backup.html", current_month=today.month, current_year=today.year, years=list(range(today.year - 5, today.year + 2)), month_names=list(calendar.month_name)[1:])


@app.route("/admin/backup/download")
def download_backup():
    if not _admin_ok():
        return redirect(url_for("admin_login"))
    kind = request.args.get("backup_type", "complete")
    month = int(request.args.get("month", date.today().month)) if kind == "monthly" else None
    year = int(request.args.get("year", date.today().year)) if kind == "monthly" else None
    if kind == "monthly" and (month < 1 or month > 12 or year < 2000 or year > 2100):
        return redirect(url_for("backup_page"))
    wb = _build(month, year)
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"IESC_Backup_{year}_{month:02d}.xlsx" if kind == "monthly" else f"IESC_Complete_Backup_{date.today().isoformat()}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.after_request
def _add_backup_button(response):
    if request.path == "/admin" and response.status_code == 200 and response.content_type.startswith("text/html"):
        try:
            html = response.get_data(as_text=True)
            marker = "<!-- System -->"
            if marker in html and "/admin/backup" not in html:
                block = '<!-- Backup & Reports -->\n        <div class="btn-group">\n            <div class="group-label">💾 Backup & Reports</div>\n            <div class="btn-row">\n                <a href="/admin/backup" class="btn btn-teal">📥 Excel Backup & Reports</a>\n            </div>\n        </div>\n\n\n        '
                response.set_data(html.replace(marker, block + marker, 1))
        except Exception as exc:
            print(f"Backup dashboard injection error: {exc}")
    return response


if __name__ == "__main__":
    app.run(debug=True)
