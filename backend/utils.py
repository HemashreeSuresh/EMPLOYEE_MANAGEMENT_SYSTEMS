"""Shared helper utilities to avoid circular imports."""

import base64
import csv
import hashlib
import hmac
import json
import os
import re
import time
from functools import wraps
from io import BytesIO, StringIO

from flask import current_app, flash, g, make_response, redirect, request, session, url_for
from werkzeug.utils import secure_filename

from models import ActivityLog, User, db


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\d{10,15}$")
TASK_STATUS_VALUES = {"Assigned", "In Progress", "Completed"}


def log_activity(action_text):
    """Save activity logs for authenticated users."""
    user_id = session.get("user_id")
    if user_id:
        db.session.add(ActivityLog(user_id=user_id, action=action_text))
        db.session.commit()


def login_required(view_func):
    """Protect a route and force user login."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapped


def roles_required(*allowed_roles):
    """Protect a route and allow only listed roles."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("auth.login"))

            current_role = session.get("role")
            if current_role not in allowed_roles:
                flash("You are not authorized to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def api_auth_required(*allowed_roles):
    """JWT auth decorator for API routes."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            token = get_bearer_token()
            if not token:
                return {"error": "Missing Bearer token"}, 401

            payload = decode_jwt(token)
            if not payload:
                return {"error": "Invalid or expired token"}, 401

            user_id = payload.get("user_id")
            role = payload.get("role")
            user = User.query.get(user_id) if user_id else None

            if not user or user.role != role:
                return {"error": "Unauthorized user"}, 401
            if allowed_roles and user.role not in allowed_roles:
                return {"error": "Forbidden"}, 403

            g.api_user = user
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def create_pdf_table(filename, title, headers, rows):
    """Generate a simple table PDF response using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        styles = getSampleStyleSheet()

        table_data = [headers] + rows
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )

        story = [Paragraph(title, styles["Title"]), Spacer(1, 10), table]
        doc.build(story)

        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        # Fallback keeps export working even if PDF dependency/runtime fails.
        fallback_name = filename[:-4] + ".csv" if filename.lower().endswith(".pdf") else f"{filename}.csv"
        return create_csv_table(fallback_name, headers, rows)


def create_csv_table(filename, headers, rows):
    """Generate CSV response as a fallback export format."""
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    response = make_response(csv_buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def allowed_file(filename):
    """Allow limited upload file extensions."""
    allowed = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "txt", "zip"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_uploaded_file(upload_file):
    """Save file into static/uploads and return relative path."""
    clean_name = secure_filename(upload_file.filename)
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    final_name = f"{timestamp}_{clean_name}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    full_path = os.path.join(upload_folder, final_name)
    upload_file.save(full_path)
    return full_path.replace("\\", "/")


def is_valid_email(value):
    return bool(EMAIL_RE.match(value or ""))


def is_valid_phone(value):
    return bool(PHONE_RE.match(value or ""))


def is_valid_iso_date(value):
    if not value:
        return False
    try:
        from datetime import datetime

        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _b64url_encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")


def _b64url_decode(raw_text):
    padding = "=" * (-len(raw_text) % 4)
    return base64.urlsafe_b64decode((raw_text + padding).encode("utf-8"))


def create_jwt(payload, expires_in=3600):
    secret = current_app.config["SECRET_KEY"]
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    body = dict(payload)
    body["iat"] = now
    body["exp"] = now + int(expires_in)

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")

    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt(token):
    if not token or token.count(".") != 2:
        return None

    secret = current_app.config["SECRET_KEY"]
    header_segment, payload_segment, signature_segment = token.split(".")
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()

    try:
        provided_signature = _b64url_decode(signature_segment)
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    return payload


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if auth_header.startswith(prefix):
        return auth_header[len(prefix) :].strip()
    return None
