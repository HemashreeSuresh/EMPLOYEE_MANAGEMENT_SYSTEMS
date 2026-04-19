"""Employee routes: profile, attendance marking, announcements, salary view."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models import ActivityLog, Announcement, Attendance, DutySchedule, Employee, LeaveRequest, RelaxationTime, TaskAssignment, db
from utils import allowed_file, log_activity, login_required, roles_required, save_uploaded_file


employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


@employee_bp.route("/dashboard")
@login_required
@roles_required("Employee", "Admin")
def dashboard():
    current = Employee.query.filter_by(user_id=session.get("user_id")).first()
    attendance_count = 0
    if current:
        attendance_count = Attendance.query.filter_by(employee_id=current.id).count()
    items = Announcement.query.order_by(Announcement.id.desc()).limit(5).all()
    return render_template("employee/dashboard.html", employee=current, attendance_count=attendance_count, items=items)


@employee_bp.route("/profile", methods=["GET", "POST"])
@login_required
@roles_required("Employee", "Admin")
def profile():
    row = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()

    if request.method == "POST":
        row.phone = request.form.get("phone", "").strip()
        row.email = request.form.get("email", "").strip().lower()
        db.session.commit()
        log_activity("Updated own profile")
        flash("Profile updated.", "success")
        return redirect(url_for("employee.profile"))

    return render_template("employee/profile.html", employee=row)


@employee_bp.route("/attendance", methods=["GET", "POST"])
@login_required
@roles_required("Employee", "Admin")
def attendance():
    row = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    today = str(datetime.now().date())

    if request.method == "POST":
        status = request.form.get("status", "").strip()
        existing = Attendance.query.filter_by(employee_id=row.id, date=today).first()

        if existing:
            existing.status = status
            existing.approved_by = None
        else:
            db.session.add(Attendance(employee_id=row.id, date=today, status=status, approved_by=None))

        db.session.commit()
        log_activity("Marked attendance")
        flash("Attendance submitted for approval.", "success")
        return redirect(url_for("employee.attendance"))

    records = Attendance.query.filter_by(employee_id=row.id).order_by(Attendance.id.desc()).all()
    return render_template("employee/attendance.html", records=records, today=today)


@employee_bp.route("/announcements")
@login_required
@roles_required("Employee", "Admin")
def announcements():
    items = Announcement.query.order_by(Announcement.id.desc()).all()
    return render_template("employee/announcements.html", items=items)


@employee_bp.route("/salary")
@login_required
@roles_required("Employee", "Admin")
def salary():
    row = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    return render_template("employee/salary.html", employee=row)


@employee_bp.route("/tasks")
@login_required
@roles_required("Employee", "Admin")
def tasks():
    """Employee views assigned tasks and current progress."""
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    rows = TaskAssignment.query.filter_by(employee_id=emp.id).order_by(TaskAssignment.id.desc()).all()
    return render_template("employee/tasks.html", tasks=rows)


@employee_bp.route("/work-activity")
@login_required
@roles_required("Employee", "Admin")
def work_activity():
    """Employee work activity summary with recent actions."""
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()

    task_total = TaskAssignment.query.filter_by(employee_id=emp.id).count()
    completed_tasks = TaskAssignment.query.filter_by(employee_id=emp.id, status="Completed").count()
    in_progress_tasks = TaskAssignment.query.filter_by(employee_id=emp.id, status="In Progress").count()
    attendance_total = Attendance.query.filter_by(employee_id=emp.id).count()
    leave_total = LeaveRequest.query.filter_by(employee_id=emp.id).count()
    relaxation_total = RelaxationTime.query.filter_by(employee_id=emp.id).count()

    recent_tasks = TaskAssignment.query.filter_by(employee_id=emp.id).order_by(TaskAssignment.id.desc()).limit(5).all()
    recent_logs = ActivityLog.query.filter_by(user_id=session.get("user_id")).order_by(ActivityLog.timestamp.desc()).limit(10).all()

    return render_template(
        "employee/work_activity.html",
        employee=emp,
        task_total=task_total,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        attendance_total=attendance_total,
        leave_total=leave_total,
        relaxation_total=relaxation_total,
        recent_tasks=recent_tasks,
        recent_logs=recent_logs,
    )


@employee_bp.route("/tasks/update/<int:task_id>", methods=["POST"])
@login_required
@roles_required("Employee", "Admin")
def update_task(task_id):
    """Employee updates own task progress report."""
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    task = TaskAssignment.query.get_or_404(task_id)

    if task.employee_id != emp.id:
        flash("You can only update your own tasks.", "danger")
        return redirect(url_for("employee.tasks"))

    task.status = request.form.get("status", "").strip()
    task.progress_notes = request.form.get("progress_notes", "").strip()

    work_file = request.files.get("work_file")
    if work_file and work_file.filename:
        if not allowed_file(work_file.filename):
            flash("Invalid work file type.", "danger")
            return redirect(url_for("employee.tasks"))
        task.work_file_path = save_uploaded_file(work_file)
        task.work_file_uploaded_at = datetime.utcnow()

    db.session.commit()
    log_activity(f"Updated progress for task ID {task_id}")
    flash("Task progress updated.", "success")
    return redirect(url_for("employee.tasks"))


@employee_bp.route("/relaxation-time", methods=["GET", "POST"])
@login_required
@roles_required("Employee", "Admin")
def relaxation_time():
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    today = str(datetime.now().date())

    if request.method == "POST":
        relax_date = request.form.get("relax_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        reason = request.form.get("reason", "").strip()

        if not all([relax_date, start_time, end_time]):
            flash("Date, start time and end time are required.", "danger")
            return redirect(url_for("employee.relaxation_time"))

        if start_time >= end_time:
            flash("End time must be later than start time.", "danger")
            return redirect(url_for("employee.relaxation_time"))

        db.session.add(
            RelaxationTime(
                employee_id=emp.id,
                relax_date=relax_date,
                start_time=start_time,
                end_time=end_time,
                reason=reason,
            )
        )
        db.session.commit()
        log_activity(f"Submitted relaxation time for {relax_date}")
        flash("Relaxation time added successfully.", "success")
        return redirect(url_for("employee.relaxation_time"))

    rows = RelaxationTime.query.filter_by(employee_id=emp.id).order_by(RelaxationTime.id.desc()).all()
    return render_template("employee/relaxation_time.html", rows=rows, today=today)


@employee_bp.route("/duty-schedule")
@login_required
@roles_required("Employee", "Admin")
def duty_schedule():
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()
    rows = DutySchedule.query.filter_by(employee_id=emp.id).order_by(DutySchedule.id.desc()).all()
    return render_template("employee/duty_schedule.html", rows=rows)


@employee_bp.route("/leave", methods=["GET", "POST"])
@login_required
@roles_required("Employee", "Admin")
def leave_requests():
    """Employee submits leave requests; manager reviews them."""
    emp = Employee.query.filter_by(user_id=session.get("user_id")).first_or_404()

    if request.method == "POST":
        leave_type = request.form.get("leave_type", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        reason = request.form.get("reason", "").strip()

        if not all([leave_type, start_date, end_date, reason]):
            flash("All leave fields are required.", "danger")
            return redirect(url_for("employee.leave_requests"))

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("employee.leave_requests"))

        if end_dt < start_dt:
            flash("End date cannot be before start date.", "danger")
            return redirect(url_for("employee.leave_requests"))

        db.session.add(
            LeaveRequest(
                employee_id=emp.id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status="Pending",
            )
        )
        db.session.commit()
        log_activity(f"Employee '{emp.full_name}' submitted leave request ({start_date} to {end_date})")
        flash("Leave request submitted for manager approval.", "success")
        return redirect(url_for("employee.leave_requests"))

    rows = LeaveRequest.query.filter_by(employee_id=emp.id).order_by(LeaveRequest.created_at.desc()).all()
    return render_template("employee/leave.html", rows=rows)
