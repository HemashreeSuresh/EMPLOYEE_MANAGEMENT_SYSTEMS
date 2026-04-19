"""Application entry point for Employee Management System."""

import os
from datetime import datetime

from flask import Flask, g, redirect, session, url_for
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from models import Announcement, Employee, User, db
from utils import login_required


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app = Flask(
    __name__,
    static_folder=os.path.join(FRONTEND_DIR, "static"),
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
)


def get_database_uri():
    """Prefer hosted database configuration, with SQLite as a local fallback."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url
    local_db = os.path.abspath(os.path.join(BASE_DIR, "database.db")).replace("\\", "/")
    return f"sqlite:///{local_db}"


# Core configuration
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(FRONTEND_DIR, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

db.init_app(app)


@app.before_request
def load_current_user():
    """Expose logged in user in flask global context."""
    g.user = None
    if "user_id" in session:
        g.user = User.query.get(session["user_id"])


@app.context_processor
def inject_globals():
    """Provide common template context."""
    return {"current_year": datetime.now().year}


@app.after_request
def add_secure_headers(response):
    """Attach baseline security headers without changing page behavior."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'"
    )
    return response


@app.route("/")
def root():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth.login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Redirect user to role-specific dashboard."""
    role = session.get("role")
    if role == "Admin":
        return redirect(url_for("admin.dashboard"))
    if role == "HR":
        return redirect(url_for("hr.dashboard"))
    if role == "Manager":
        return redirect(url_for("manager.dashboard"))
    return redirect(url_for("employee.dashboard"))


def ensure_schema_and_seed():
    """Create database and seed default data (safe for demo use)."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    # Rebuild old schema automatically for this project version.
    required_tables = {
        "user",
        "employee",
        "attendance",
        "document",
        "announcement",
        "activity_log",
        "task_assignment",
        "duty_schedule",
        "relaxation_time",
        "leave_request",
        "burnout_score",
        "alert",
        "interview_session",
    }
    needs_rebuild = table_names and not required_tables.issubset(set(table_names))
    if not needs_rebuild and "employee" in table_names:
        employee_columns = {col["name"] for col in inspector.get_columns("employee")}
        required_employee_columns = {"team", "skill_tags", "manager_id"}
        if not required_employee_columns.issubset(employee_columns):
            needs_rebuild = True
    if not needs_rebuild and "task_assignment" in table_names:
        task_columns = {col["name"] for col in inspector.get_columns("task_assignment")}
        required_task_columns = {"work_file_path", "work_file_uploaded_at"}
        if not required_task_columns.issubset(task_columns):
            needs_rebuild = True

    if needs_rebuild:
        db.drop_all()

    db.create_all()

    # Seed users only if empty.
    if User.query.count() == 0:
        admin = User(username="admin", password_hash=generate_password_hash("admin123"), role="Admin")
        hr = User(username="hr", password_hash=generate_password_hash("hr123"), role="HR")
        manager = User(username="manager", password_hash=generate_password_hash("manager123"), role="Manager")
        employee_user = User(
            username="employee", password_hash=generate_password_hash("employee123"), role="Employee"
        )
        db.session.add_all([admin, hr, manager, employee_user])
        db.session.commit()

        emp = Employee(
            full_name="Demo Employee",
            email="employee@example.com",
            phone="9876543210",
            department="Engineering",
            designation="Junior Developer",
            salary=30000,
            joining_date="2025-01-15",
            user_id=employee_user.id,
        )
        db.session.add(emp)

        db.session.add(
            Announcement(
                title="Welcome to EMS",
                content="System is ready. Please update profiles and attendance daily.",
                date=str(datetime.now().date()),
            )
        )
        db.session.commit()


# Register blueprints after helpers to avoid circular imports.
from routes.admin import admin_bp  # noqa: E402
from routes.api import api_bp  # noqa: E402
from routes.auth import auth_bp  # noqa: E402
from routes.employee import employee_bp  # noqa: E402
from routes.hr import hr_bp  # noqa: E402
from routes.manager import manager_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(api_bp)


with app.app_context():
    ensure_schema_and_seed()


if __name__ == "__main__":
    # Only run dev server locally, not in Vercel
    app.run(debug=True)
