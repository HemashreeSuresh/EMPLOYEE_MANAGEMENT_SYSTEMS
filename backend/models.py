"""Database models for Employee Management System."""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    """Application users used for authentication and role-based access."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Admin, HR, Manager, Employee

    employee = db.relationship("Employee", back_populates="user", uselist=False)


class Employee(db.Model):
    """Master employee profile table."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    designation = db.Column(db.String(80), nullable=False)
    salary = db.Column(db.Float, nullable=False)
    joining_date = db.Column(db.String(20), nullable=False)
    team = db.Column(db.String(80), nullable=True)
    skill_tags = db.Column(db.String(255), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=True)
    user = db.relationship("User", back_populates="employee")
    manager = db.relationship("Employee", remote_side=[id], backref="reportees")


class Attendance(db.Model):
    """Daily attendance records."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    employee = db.relationship("Employee", backref="attendance_records")


class Document(db.Model):
    """Uploaded employee documents."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="documents")


class TaskAssignment(db.Model):
    """Daily tasks assigned by HR and updated by employees."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Assigned")
    progress_notes = db.Column(db.Text, nullable=True)
    work_file_path = db.Column(db.String(255), nullable=True)
    work_file_uploaded_at = db.Column(db.DateTime, nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    employee = db.relationship("Employee", backref="tasks")


class Announcement(db.Model):
    """Announcement board posts visible to all users."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(20), nullable=False)


class ActivityLog(db.Model):
    """Tracks important actions for auditing."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="activity_logs")


class LeaveRequest(db.Model):
    """Leave requests raised by employees and reviewed by managers/HR."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    leave_type = db.Column(db.String(30), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    manager_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="leave_requests")


class BurnoutScore(db.Model):
    """Computed burnout indicator for proactive HR intervention."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    factors_json = db.Column(db.Text, nullable=True)
    generated_on = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="burnout_scores")


class Alert(db.Model):
    """In-app alerts delivered to users for actionable events."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="alerts")


class DutySchedule(db.Model):
    """Duty slots assigned by manager for employees."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    duty_date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="duty_schedules")


class RelaxationTime(db.Model):
    """Employee relaxation/break entries for a work day."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    relax_date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="relaxation_entries")


class InterviewSession(db.Model):
    """HR interview notes and answers for employees."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    interviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question_answers_json = db.Column(db.Text, nullable=False)
    overall_notes = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.String(20), nullable=False, default="Pending")
    interviewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", backref="interview_sessions")
    interviewer = db.relationship("User", backref="interview_sessions")
