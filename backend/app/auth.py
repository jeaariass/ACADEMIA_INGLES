from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .models import User
from .security import (
    clear_login_failures,
    login_is_rate_limited,
    record_login_failure,
)


auth_bp = Blueprint("auth", __name__)
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-account-password")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()[:80]
        password = request.form.get("password") or ""

        limited, retry_seconds = login_is_rate_limited(username)
        if limited:
            flash(
                f"Too many failed sign-in attempts. Try again in about {max(1, retry_seconds // 60)} minute(s).",
                "warning",
            )
            return render_template("login.html"), 429

        user = User.query.filter_by(username=username).first() if username else None
        valid = user.check_password(password) if user else check_password_hash(_DUMMY_PASSWORD_HASH, password)

        if user and valid:
            clear_login_failures(username)
            # Prevent session fixation. A fresh CSRF token is generated on the next page.
            session.clear()
            session.permanent = True
            login_user(user)
            return redirect(url_for("main.dashboard"))

        record_login_failure(username)
        flash("Incorrect username or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
