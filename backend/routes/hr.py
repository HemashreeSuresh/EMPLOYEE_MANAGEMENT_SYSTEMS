"""HR routes: employees CRUD, attendance management, document uploads."""

import json
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from utils import allowed_file, log_activity, login_required, roles_required, save_uploaded_file
from models import Alert, Announcement, Attendance, BurnoutScore, Document, Employee, InterviewSession, LeaveRequest, TaskAssignment, User, db


hr_bp = Blueprint("hr", __name__, url_prefix="/hr")

INTERVIEW_QUESTIONS = [
    "Tell us about yourself and your background.",
    "Why do you want to join this role and our organization?",
    "What relevant skills or experience do you bring to this position?",
    "How do you handle deadlines, pressure, or challenging work situations?",
    "What are your strengths, and what area would you like to improve?",
]


@hr_bp.route("/dashboard")
@login_required
@roles_required("HR", "Admin")
def dashboard():
    employee_count = Employee.query.count()
    today = str(datetime.now().date())
    today_attendance = Attendance.query.filter_by(date=today).count()
    pending_attendance = Attendance.query.filter_by(status="Pending").count()
    return render_template(
        "hr/dashboard.html",
        employee_count=employee_count,
        today_attendance=today_attendance,
        pending_attendance=pending_attendance,
    )


@hr_bp.route("/employees")
@login_required
@roles_required("HR", "Admin")
def employees():
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()

    query = Employee.query
    if search:
        query = query.filter(
            (Employee.full_name.ilike(f"%{search}%"))
            | (Employee.department.ilike(f"%{search}%"))
            | (Employee.designation.ilike(f"%{search}%"))
        )

    if role_filter:
        query = query.join(Employee.user).filter(User.role == role_filter)

    rows = query.order_by(Employee.id.desc()).all()
    return render_template("hr/employees.html", employees=rows, search=search, role_filter=role_filter)


@hr_bp.route("/employees/add", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin")
def add_employee():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()
        salary = request.form.get("salary", "").strip()
        joining_date = request.form.get("joining_date", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip() or "Employee"

        if not all([full_name, email, phone, department, designation, salary, joining_date, username, password]):
            flash("All fields are required.", "danger")
            return redirect(url_for("hr.add_employee"))

        if Employee.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("hr.add_employee"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("hr.add_employee"))

        if role not in ["Admin", "HR", "Manager", "Employee"]:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("hr.add_employee"))

        try:
            salary_value = float(salary)
        except ValueError:
            flash("Salary must be a valid number.", "danger")
            return redirect(url_for("hr.add_employee"))

        user = User(username=username, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.flush()

        row = Employee(
            full_name=full_name,
            email=email,
            phone=phone,
            department=department,
            designation=designation,
            salary=salary_value,
            joining_date=joining_date,
            user_id=user.id,
        )
        db.session.add(row)
        db.session.commit()
        log_activity(f"Added employee '{full_name}' with login user '{username}'")
        flash("Employee and login account added successfully.", "success")
        return redirect(url_for("hr.employees"))

    return render_template("hr/add_employee.html")


@hr_bp.route("/employees/edit/<int:employee_id>", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin")
def edit_employee(employee_id):
    row = Employee.query.get_or_404(employee_id)

    if request.method == "POST":
        row.full_name = request.form.get("full_name", "").strip()
        row.email = request.form.get("email", "").strip().lower()
        row.phone = request.form.get("phone", "").strip()
        row.department = request.form.get("department", "").strip()
        row.designation = request.form.get("designation", "").strip()
        row.salary = float(request.form.get("salary", "0"))
        row.joining_date = request.form.get("joining_date", "").strip()

        db.session.commit()
        log_activity(f"Updated employee '{row.full_name}'")
        flash("Employee updated.", "success")
        return redirect(url_for("hr.employees"))

    return render_template("hr/edit_employee.html", employee=row)


@hr_bp.route("/employees/delete/<int:employee_id>", methods=["POST"])
@login_required
@roles_required("HR", "Admin")
def delete_employee(employee_id):
    row = Employee.query.get_or_404(employee_id)
    linked_user = row.user

    if linked_user and linked_user.id == session.get("user_id"):
        flash("You cannot delete your own logged-in account.", "danger")
        return redirect(url_for("hr.employees"))

    db.session.delete(row)
    if linked_user:
        db.session.delete(linked_user)
    db.session.commit()
    log_activity(f"Deleted employee '{row.full_name}' and linked login account")
    flash("Employee and linked login account deleted.", "info")
    return redirect(url_for("hr.employees"))


@hr_bp.route("/attendance")
@login_required
@roles_required("HR", "Admin")
def attendance():
    rows = Attendance.query.order_by(Attendance.id.desc()).all()
    return render_template("hr/attendance.html", rows=rows)


@hr_bp.route("/documents", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin")
def documents():
    if request.method == "POST":
        employee_id = request.form.get("employee_id", type=int)
        file_obj = request.files.get("document")

        if not employee_id or not file_obj or file_obj.filename == "":
            flash("Employee and document are required.", "danger")
            return redirect(url_for("hr.documents"))

        if not allowed_file(file_obj.filename):
            flash("Invalid file type.", "danger")
            return redirect(url_for("hr.documents"))

        path = save_uploaded_file(file_obj)
        db.session.add(Document(employee_id=employee_id, file_path=path, uploaded_by=session.get("user_id")))
        db.session.commit()
        log_activity(f"Uploaded document for employee ID {employee_id}")
        flash("Document uploaded.", "success")
        return redirect(url_for("hr.documents"))

    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    docs = Document.query.order_by(Document.id.desc()).all()
    return render_template("hr/documents.html", employees=employees, docs=docs)


@hr_bp.route("/announcements")
@login_required
@roles_required("HR", "Admin")
def announcements():
    items = Announcement.query.order_by(Announcement.id.desc()).all()
    return render_template("hr/announcements.html", items=items)


@hr_bp.route("/tasks", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin")
def tasks():
    """HR assigns daily tasks and monitors progress."""
    if request.method == "POST":
        employee_id = request.form.get("employee_id", type=int)
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()

        if not all([employee_id, title, description, due_date]):
            flash("All task fields are required.", "danger")
            return redirect(url_for("hr.tasks"))

        task = TaskAssignment(
            employee_id=employee_id,
            title=title,
            description=description,
            due_date=due_date,
            status="Assigned",
            progress_notes="",
            assigned_by=session.get("user_id"),
        )
        db.session.add(task)
        db.session.commit()
        log_activity(f"Assigned task '{title}' to employee ID {employee_id}")
        flash("Task assigned successfully.", "success")
        return redirect(url_for("hr.tasks"))

    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    tasks_list = TaskAssignment.query.order_by(TaskAssignment.id.desc()).all()
    return render_template("hr/tasks.html", employees=employees, tasks=tasks_list)


@hr_bp.route("/analytics")
@login_required
@roles_required("HR", "Admin")
def analytics():
    """HR analytics page with leave and burnout summaries."""
    pending_leave = LeaveRequest.query.filter_by(status="Pending").count()
    approved_leave = LeaveRequest.query.filter_by(status="Approved").count()
    rejected_leave = LeaveRequest.query.filter_by(status="Rejected").count()
    high_risk_count = BurnoutScore.query.filter(BurnoutScore.risk_level.in_(["Medium", "High"])).count()
    top_risk = (
        BurnoutScore.query.order_by(BurnoutScore.generated_on.desc(), BurnoutScore.score.desc()).limit(8).all()
    )
    return render_template(
        "hr/analytics.html",
        pending_leave=pending_leave,
        approved_leave=approved_leave,
        rejected_leave=rejected_leave,
        high_risk_count=high_risk_count,
        top_risk=top_risk,
    )


@hr_bp.route("/interviews", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin")
def interviews():
    """HR interview page for employees."""
    employees = Employee.query.order_by(Employee.id.desc()).all()
    selected_employee_id = request.args.get("employee_id", type=int)

    if request.method == "POST":
        selected_employee_id = request.form.get("employee_id", type=int)
        overall_notes = request.form.get("overall_notes", "").strip()
        recommendation = request.form.get("recommendation", "Pending").strip()
        answers = [request.form.get(f"answer_{index}", "").strip() for index in range(len(INTERVIEW_QUESTIONS))]

        employee = Employee.query.get_or_404(selected_employee_id)

        if recommendation not in ["Pending", "Selected", "Rejected", "Hold"]:
            flash("Invalid interview recommendation.", "danger")
            return redirect(url_for("hr.interviews", employee_id=selected_employee_id))

        if not any(answers):
            flash("Please record at least one interview answer.", "danger")
            return redirect(url_for("hr.interviews", employee_id=selected_employee_id))

        payload = [{"question": question, "answer": answer} for question, answer in zip(INTERVIEW_QUESTIONS, answers)]

        db.session.add(
            InterviewSession(
                employee_id=employee.id,
                interviewed_by=session.get("user_id"),
                question_answers_json=json.dumps(payload),
                overall_notes=overall_notes,
                recommendation=recommendation,
            )
        )
        db.session.commit()
        log_activity(f"Completed interview for employee '{employee.full_name}'")
        flash("Interview details saved successfully.", "success")
        return redirect(url_for("hr.interviews", employee_id=employee.id))

    selected_employee = None
    parsed_sessions = []

    if selected_employee_id:
        selected_employee = Employee.query.get_or_404(selected_employee_id)
        sessions = (
            InterviewSession.query.filter_by(employee_id=selected_employee.id)
            .order_by(InterviewSession.interviewed_at.desc())
            .all()
        )
        for interview in sessions:
            try:
                answers = json.loads(interview.question_answers_json)
            except json.JSONDecodeError:
                answers = []
            parsed_sessions.append({"session": interview, "answers": answers})

    return render_template(
        "hr/interviews.html",
        employees=employees,
        selected_employee=selected_employee,
        selected_employee_id=selected_employee_id,
        interview_questions=INTERVIEW_QUESTIONS,
        parsed_sessions=parsed_sessions,
    )


@hr_bp.route("/alerts", methods=["GET", "POST"])
@login_required
@roles_required("HR", "Admin", "Manager", "Employee")
def alerts():
    """List in-app alerts and allow mark-as-read."""
    if request.method == "POST":
        alert_id = request.form.get("alert_id", type=int)
        row = Alert.query.filter_by(id=alert_id, user_id=session.get("user_id")).first()
        if row:
            row.is_read = True
            db.session.commit()
            flash("Alert marked as read.", "success")
        else:
            flash("Alert not found.", "danger")
        return redirect(url_for("hr.alerts"))

    rows = Alert.query.filter_by(user_id=session.get("user_id")).order_by(Alert.created_at.desc()).all()
    return render_template("hr/alerts.html", rows=rows)
