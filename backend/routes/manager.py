"""Manager routes: team view, attendance approvals, duty scheduling and reports."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models import ActivityLog, Alert, Attendance, DutySchedule, Employee, LeaveRequest, RelaxationTime, TaskAssignment, db
from utils import create_pdf_table, log_activity, login_required, roles_required


manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


@manager_bp.route("/dashboard")
@login_required
@roles_required("Manager", "Admin")
def dashboard():
    total_team = Employee.query.count()
    pending_attendance = Attendance.query.filter_by(status="Pending").count()
    approved_attendance = Attendance.query.filter_by(status="Approved").count()
    pending_leave_requests = LeaveRequest.query.filter_by(status="Pending").count()

    department_counts = {}
    for row in Employee.query.all():
        department_counts[row.department] = department_counts.get(row.department, 0) + 1

    return render_template(
        "manager/dashboard.html",
        total_team=total_team,
        pending_attendance=pending_attendance,
        approved_attendance=approved_attendance,
        pending_leave_requests=pending_leave_requests,
        department_counts=department_counts,
    )


@manager_bp.route("/work-activity")
@login_required
@roles_required("Manager", "Admin")
def work_activity():
    """Manager view of current employee work activity."""
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    activity_rows = []

    for employee in employees:
        tasks = TaskAssignment.query.filter_by(employee_id=employee.id).order_by(TaskAssignment.id.desc()).all()
        attendance_rows = Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.id.desc()).all()
        leave_rows = LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).all()
        relaxation_rows = RelaxationTime.query.filter_by(employee_id=employee.id).order_by(RelaxationTime.id.desc()).all()
        latest_log = None

        if employee.user_id:
            latest_log = ActivityLog.query.filter_by(user_id=employee.user_id).order_by(ActivityLog.timestamp.desc()).first()

        activity_rows.append(
            {
                "employee": employee,
                "task_total": len(tasks),
                "completed_tasks": sum(1 for task in tasks if task.status == "Completed"),
                "in_progress_tasks": sum(1 for task in tasks if task.status == "In Progress"),
                "latest_task": tasks[0] if tasks else None,
                "attendance_total": len(attendance_rows),
                "latest_attendance": attendance_rows[0] if attendance_rows else None,
                "pending_leaves": sum(1 for leave in leave_rows if leave.status == "Pending"),
                "relaxation_total": len(relaxation_rows),
                "latest_log": latest_log,
            }
        )

    return render_template("manager/work_activity.html", activity_rows=activity_rows)


@manager_bp.route("/team")
@login_required
@roles_required("Manager", "Admin")
def team():
    rows = Employee.query.order_by(Employee.full_name.asc()).all()
    return render_template("manager/team.html", employees=rows)


@manager_bp.route("/attendance")
@login_required
@roles_required("Manager", "Admin")
def attendance():
    rows = Attendance.query.order_by(Attendance.id.desc()).all()
    return render_template("manager/attendance.html", rows=rows)


@manager_bp.route("/reports/attendance/pdf")
@login_required
@roles_required("Manager", "Admin")
def attendance_report_pdf():
    rows = Attendance.query.order_by(Attendance.id.desc()).all()
    headers = ["ID", "Employee Name", "Date", "Status", "Approved By"]
    data = [[r.id, r.employee.full_name if r.employee else "-", r.date, r.status, r.approved_by or "-"] for r in rows]
    log_activity("Downloaded attendance PDF report")
    return create_pdf_table("attendance_report.pdf", "Attendance Report", headers, data)


@manager_bp.route("/duty-schedule", methods=["GET", "POST"])
@login_required
@roles_required("Manager", "Admin")
def duty_schedule():
    if request.method == "POST":
        employee_id = request.form.get("employee_id", type=int)
        duty_date = request.form.get("duty_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        notes = request.form.get("notes", "").strip()

        if not all([employee_id, duty_date, start_time, end_time]):
            flash("Employee, date, start time and end time are required.", "danger")
            return redirect(url_for("manager.duty_schedule"))

        if start_time >= end_time:
            flash("End time must be later than start time.", "danger")
            return redirect(url_for("manager.duty_schedule"))

        row = DutySchedule(
            employee_id=employee_id,
            duty_date=duty_date,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            assigned_by=session.get("user_id"),
        )
        db.session.add(row)
        db.session.commit()
        log_activity(f"Assigned duty schedule to employee ID {employee_id} on {duty_date}")
        flash("Duty schedule assigned successfully.", "success")
        return redirect(url_for("manager.duty_schedule"))

    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    rows = DutySchedule.query.order_by(DutySchedule.id.desc()).all()
    return render_template("manager/duty_schedule.html", employees=employees, rows=rows)


@manager_bp.route("/relaxation-times")
@login_required
@roles_required("Manager", "Admin")
def relaxation_times():
    rows = RelaxationTime.query.order_by(RelaxationTime.id.desc()).all()
    return render_template("manager/relaxation_times.html", rows=rows)


@manager_bp.route("/leave-approvals")
@login_required
@roles_required("Manager", "Admin")
def leave_approvals():
    """Manager reviews all leave requests."""
    rows = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()
    return render_template("manager/leave_approvals.html", rows=rows)


@manager_bp.route("/leave-approvals/<int:leave_id>/decision", methods=["POST"])
@login_required
@roles_required("Manager", "Admin")
def decide_leave(leave_id):
    """Manager approves or rejects employee leave request."""
    row = LeaveRequest.query.get_or_404(leave_id)
    decision = request.form.get("decision", "").strip()
    manager_note = request.form.get("manager_note", "").strip()

    if decision not in ["Approved", "Rejected"]:
        flash("Invalid leave decision.", "danger")
        return redirect(url_for("manager.leave_approvals"))

    row.status = decision
    row.manager_note = manager_note
    db.session.commit()

    if row.employee and row.employee.user_id:
        db.session.add(
            Alert(
                user_id=row.employee.user_id,
                alert_type="Leave",
                message=f"Your leave request ({row.start_date} to {row.end_date}) was {decision.lower()} by manager.",
            )
        )
        db.session.commit()

    log_activity(f"Manager {decision.lower()} leave request #{row.id}")
    flash(f"Leave request {decision.lower()}.", "success")
    return redirect(url_for("manager.leave_approvals"))
