"""Admin routes: analytics, user management, reports, logs, announcements."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from utils import create_pdf_table, log_activity, login_required, roles_required
from models import ActivityLog, Announcement, Attendance, BurnoutScore, Employee, LeaveRequest, User, db


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@roles_required("Admin")
def dashboard():
    employee_count = Employee.query.count()
    attendance_count = Attendance.query.count()
    approved_attendance = Attendance.query.filter_by(status="Approved").count()
    user_count = User.query.count()
    role_labels = ["Admin", "HR", "Manager", "Employee"]

    role_counts = {
        "Admin": User.query.filter_by(role="Admin").count(),
        "HR": User.query.filter_by(role="HR").count(),
        "Manager": User.query.filter_by(role="Manager").count(),
        "Employee": User.query.filter_by(role="Employee").count(),
    }
    role_values = [role_counts.get(role, 0) for role in role_labels]

    return render_template(
        "admin/dashboard.html",
        employee_count=employee_count,
        attendance_count=attendance_count,
        approved_attendance=approved_attendance,
        user_count=user_count,
        role_labels=role_labels,
        role_values=role_values,
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@roles_required("Admin")
def manage_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()

        if not all([username, password, role]):
            flash("All fields are required.", "danger")
            return redirect(url_for("admin.manage_users"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("admin.manage_users"))

        user = User(username=username, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        log_activity(f"Created user '{username}' with role '{role}'")
        flash("User created.", "success")
        return redirect(url_for("admin.manage_users"))

    users = User.query.order_by(User.id.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/update-role/<int:user_id>", methods=["POST"])
@login_required
@roles_required("Admin")
def update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "").strip()
    if new_role not in ["Admin", "HR", "Manager", "Employee"]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.manage_users"))

    old_role = user.role
    user.role = new_role
    db.session.commit()
    log_activity(f"Updated role of '{user.username}' from '{old_role}' to '{new_role}'")
    flash("Role updated.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@roles_required("Admin")
def delete_user(user_id):
    """Delete a user account (with self-delete protection)."""
    user = User.query.get_or_404(user_id)

    if user.id == session.get("user_id"):
        flash("You cannot delete your own logged-in account.", "danger")
        return redirect(url_for("admin.manage_users"))

    linked_employee = Employee.query.filter_by(user_id=user.id).first()
    if linked_employee:
        linked_employee.user_id = None

    username = user.username
    db.session.delete(user)
    db.session.commit()
    log_activity(f"Deleted user '{username}'")
    flash("User deleted successfully.", "info")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@roles_required("Admin")
def announcements():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not all([title, content]):
            flash("Title and content are required.", "danger")
            return redirect(url_for("admin.announcements"))

        db.session.add(Announcement(title=title, content=content, date=str(datetime.now().date())))
        db.session.commit()
        log_activity(f"Posted announcement: {title}")
        flash("Announcement posted.", "success")
        return redirect(url_for("admin.announcements"))

    items = Announcement.query.order_by(Announcement.id.desc()).all()
    return render_template("admin/announcements.html", items=items)


@admin_bp.route("/logs")
@login_required
@roles_required("Admin")
def logs():
    logs_data = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template("admin/logs.html", logs=logs_data)


@admin_bp.route("/reports/employees/pdf")
@login_required
@roles_required("Admin")
def employee_report_pdf():
    employees = Employee.query.order_by(Employee.id.asc()).all()
    headers = ["ID", "Name", "Email", "Department", "Designation", "Salary"]
    rows = [[e.id, e.full_name, e.email, e.department, e.designation, f"{e.salary:.2f}"] for e in employees]
    log_activity("Downloaded employee PDF report")
    return create_pdf_table("employees_report.pdf", "Employee Report", headers, rows)


@admin_bp.route("/analytics")
@login_required
@roles_required("Admin")
def analytics():
    """Organization-level analytics for decision-making."""
    dept_rows = (
        db.session.query(Employee.department, func.count(Employee.id))
        .group_by(Employee.department)
        .order_by(func.count(Employee.id).desc())
        .all()
    )
    leave_rows = (
        db.session.query(LeaveRequest.status, func.count(LeaveRequest.id))
        .group_by(LeaveRequest.status)
        .all()
    )
    risk_rows = (
        db.session.query(BurnoutScore.risk_level, func.count(BurnoutScore.id))
        .group_by(BurnoutScore.risk_level)
        .all()
    )
    attendance_total = Attendance.query.count()
    approved_total = Attendance.query.filter_by(status="Approved").count()
    approved_pct = round((approved_total / attendance_total) * 100, 2) if attendance_total else 0
    high_risk_employees = BurnoutScore.query.filter(BurnoutScore.risk_level == "High").count()

    return render_template(
        "admin/analytics.html",
        dept_rows=dept_rows,
        leave_rows=leave_rows,
        risk_rows=risk_rows,
        approved_pct=approved_pct,
        high_risk_employees=high_risk_employees,
    )
