"""Authentication routes."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from utils import log_activity
from models import User


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash(f"Logged in as {user.role}", "success")
            log_activity("Logged in")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    if session.get("user_id"):
        log_activity("Logged out")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
