"""REST API routes with JWT auth and JSON responses."""

from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from models import ActivityLog, Employee, TaskAssignment, User, db
from utils import (
    TASK_STATUS_VALUES,
    api_auth_required,
    create_jwt,
    is_valid_email,
    is_valid_iso_date,
    is_valid_phone,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")


def _employee_to_dict(row):
    return {
        "id": row.id,
        "full_name": row.full_name,
        "email": row.email,
        "phone": row.phone,
        "department": row.department,
        "designation": row.designation,
        "salary": row.salary,
        "joining_date": row.joining_date,
        "user_id": row.user_id,
    }


def _task_to_dict(row):
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "title": row.title,
        "description": row.description,
        "due_date": row.due_date,
        "status": row.status,
        "progress_notes": row.progress_notes or "",
        "assigned_by": row.assigned_by,
    }


def _json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {}
    return payload


def _log_api_action(text):
    if getattr(g, "api_user", None):
        db.session.add(ActivityLog(user_id=g.api_user.id, action=text))
        db.session.commit()


@api_bp.errorhandler(HTTPException)
def handle_api_http_error(err):
    return jsonify({"error": err.name, "message": err.description}), err.code


@api_bp.errorhandler(Exception)
def handle_api_unexpected_error(err):
    return jsonify({"error": "Internal Server Error", "message": str(err)}), 500


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@api_bp.route("/auth/login", methods=["POST"])
def login():
    data = _json_body()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401

    token = create_jwt(
        {"user_id": user.id, "username": user.username, "role": user.role},
        expires_in=8 * 60 * 60,
    )
    return (
        jsonify(
            {
                "message": "login successful",
                "token": token,
                "user": {"id": user.id, "username": user.username, "role": user.role},
                "expires_in": 8 * 60 * 60,
            }
        ),
        200,
    )


@api_bp.route("/employees", methods=["GET"])
@api_auth_required("Admin", "HR", "Manager")
def list_employees():
    rows = Employee.query.order_by(Employee.id.desc()).all()
    return jsonify({"items": [_employee_to_dict(row) for row in rows], "count": len(rows)}), 200


@api_bp.route("/employees/<int:employee_id>", methods=["GET"])
@api_auth_required("Admin", "HR", "Manager")
def get_employee(employee_id):
    row = Employee.query.get_or_404(employee_id)
    return jsonify(_employee_to_dict(row)), 200


@api_bp.route("/employees", methods=["POST"])
@api_auth_required("Admin", "HR")
def create_employee():
    data = _json_body()

    required_fields = ["full_name", "email", "phone", "department", "designation", "salary", "joining_date"]
    missing = [field for field in required_fields if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"error": "missing required fields", "fields": missing}), 400

    email = str(data.get("email", "")).strip().lower()
    if not is_valid_email(email):
        return jsonify({"error": "invalid email format"}), 400
    if Employee.query.filter_by(email=email).first():
        return jsonify({"error": "email already exists"}), 409

    phone = str(data.get("phone", "")).strip()
    if not is_valid_phone(phone):
        return jsonify({"error": "phone must be 10 to 15 digits"}), 400

    joining_date = str(data.get("joining_date", "")).strip()
    if not is_valid_iso_date(joining_date):
        return jsonify({"error": "joining_date must be YYYY-MM-DD"}), 400

    try:
        salary = float(data.get("salary"))
        if salary <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "salary must be a positive number"}), 400

    row = Employee(
        full_name=str(data.get("full_name", "")).strip(),
        email=email,
        phone=phone,
        department=str(data.get("department", "")).strip(),
        designation=str(data.get("designation", "")).strip(),
        salary=salary,
        joining_date=joining_date,
    )
    db.session.add(row)
    db.session.commit()
    _log_api_action(f"API created employee '{row.full_name}'")
    return jsonify(_employee_to_dict(row)), 201


@api_bp.route("/employees/<int:employee_id>", methods=["PUT"])
@api_auth_required("Admin", "HR")
def update_employee(employee_id):
    row = Employee.query.get_or_404(employee_id)
    data = _json_body()

    if "email" in data:
        email = str(data.get("email", "")).strip().lower()
        if not is_valid_email(email):
            return jsonify({"error": "invalid email format"}), 400
        exists = Employee.query.filter(Employee.email == email, Employee.id != row.id).first()
        if exists:
            return jsonify({"error": "email already exists"}), 409
        row.email = email

    if "phone" in data:
        phone = str(data.get("phone", "")).strip()
        if not is_valid_phone(phone):
            return jsonify({"error": "phone must be 10 to 15 digits"}), 400
        row.phone = phone

    if "joining_date" in data:
        joining_date = str(data.get("joining_date", "")).strip()
        if not is_valid_iso_date(joining_date):
            return jsonify({"error": "joining_date must be YYYY-MM-DD"}), 400
        row.joining_date = joining_date

    if "salary" in data:
        try:
            salary = float(data.get("salary"))
            if salary <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "salary must be a positive number"}), 400
        row.salary = salary

    for text_field in ["full_name", "department", "designation"]:
        if text_field in data:
            value = str(data.get(text_field, "")).strip()
            if not value:
                return jsonify({"error": f"{text_field} cannot be empty"}), 400
            setattr(row, text_field, value)

    db.session.commit()
    _log_api_action(f"API updated employee ID {employee_id}")
    return jsonify(_employee_to_dict(row)), 200


@api_bp.route("/employees/<int:employee_id>", methods=["DELETE"])
@api_auth_required("Admin", "HR")
def delete_employee(employee_id):
    row = Employee.query.get_or_404(employee_id)
    db.session.delete(row)
    db.session.commit()
    _log_api_action(f"API deleted employee ID {employee_id}")
    return jsonify({"message": "employee deleted"}), 200


@api_bp.route("/tasks", methods=["GET"])
@api_auth_required("Admin", "HR", "Manager", "Employee")
def list_tasks():
    query = TaskAssignment.query
    user = g.api_user

    if user.role == "Employee":
        employee = Employee.query.filter_by(user_id=user.id).first_or_404()
        query = query.filter_by(employee_id=employee.id)
    else:
        employee_id = request.args.get("employee_id", type=int)
        if employee_id:
            query = query.filter_by(employee_id=employee_id)

    rows = query.order_by(TaskAssignment.id.desc()).all()
    return jsonify({"items": [_task_to_dict(row) for row in rows], "count": len(rows)}), 200


@api_bp.route("/tasks", methods=["POST"])
@api_auth_required("Admin", "HR")
def create_task():
    data = _json_body()
    required_fields = ["employee_id", "title", "description", "due_date"]
    missing = [field for field in required_fields if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"error": "missing required fields", "fields": missing}), 400

    employee_id = int(data.get("employee_id"))
    if not Employee.query.get(employee_id):
        return jsonify({"error": "employee not found"}), 404

    due_date = str(data.get("due_date", "")).strip()
    if not is_valid_iso_date(due_date):
        return jsonify({"error": "due_date must be YYYY-MM-DD"}), 400

    status = str(data.get("status", "Assigned")).strip()
    if status not in TASK_STATUS_VALUES:
        return jsonify({"error": "invalid status"}), 400

    row = TaskAssignment(
        employee_id=employee_id,
        title=str(data.get("title", "")).strip(),
        description=str(data.get("description", "")).strip(),
        due_date=due_date,
        status=status,
        progress_notes=str(data.get("progress_notes", "")).strip(),
        assigned_by=g.api_user.id,
    )
    db.session.add(row)
    db.session.commit()
    _log_api_action(f"API assigned task ID {row.id} to employee ID {employee_id}")
    return jsonify(_task_to_dict(row)), 201


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@api_auth_required("Admin", "HR", "Employee")
def update_task(task_id):
    row = TaskAssignment.query.get_or_404(task_id)
    data = _json_body()
    user = g.api_user

    if user.role == "Employee":
        employee = Employee.query.filter_by(user_id=user.id).first_or_404()
        if row.employee_id != employee.id:
            return jsonify({"error": "you can only update your own tasks"}), 403

    if "status" in data:
        status = str(data.get("status", "")).strip()
        if status not in TASK_STATUS_VALUES:
            return jsonify({"error": "invalid status"}), 400
        row.status = status

    if "progress_notes" in data:
        row.progress_notes = str(data.get("progress_notes", "")).strip()

    if "title" in data and user.role in {"Admin", "HR"}:
        title = str(data.get("title", "")).strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        row.title = title

    if "description" in data and user.role in {"Admin", "HR"}:
        description = str(data.get("description", "")).strip()
        if not description:
            return jsonify({"error": "description cannot be empty"}), 400
        row.description = description

    if "due_date" in data and user.role in {"Admin", "HR"}:
        due_date = str(data.get("due_date", "")).strip()
        if not is_valid_iso_date(due_date):
            return jsonify({"error": "due_date must be YYYY-MM-DD"}), 400
        row.due_date = due_date

    db.session.commit()
    _log_api_action(f"API updated task ID {task_id}")
    return jsonify(_task_to_dict(row)), 200


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@api_auth_required("Admin", "HR")
def delete_task(task_id):
    row = TaskAssignment.query.get_or_404(task_id)
    db.session.delete(row)
    db.session.commit()
    _log_api_action(f"API deleted task ID {task_id}")
    return jsonify({"message": "task deleted"}), 200
