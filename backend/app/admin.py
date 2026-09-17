from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .models import (
    AssessmentAttempt,
    Attempt,
    Level,
    Question,
    Topic,
    TopicProgress,
    User,
)

admin_bp = Blueprint("admin", __name__)


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Administrator access only.", "warning")
            return redirect(url_for("main.dashboard"))
        return func(*args, **kwargs)

    return wrapper


def _normalize_username(value):
    return (value or "").strip()


def _validate_role(value):
    role = (value or "student").strip().lower()
    return role if role in {"student", "admin"} else None


@admin_bp.route("/")
@login_required
@admin_required
def panel():
    users = User.query.order_by(User.role.desc(), User.full_name.asc(), User.username.asc()).all()
    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    attempts = Attempt.query.order_by(Attempt.created_at.desc()).limit(20).all()

    user_stats = {}
    for user in users:
        user_stats[user.id] = {
            "practice_attempts": Attempt.query.filter_by(user_id=user.id).count(),
            "assessment_attempts": AssessmentAttempt.query.filter_by(user_id=user.id).count(),
            "completed_lessons": TopicProgress.query.filter_by(
                user_id=user.id,
                completed=True,
            ).count(),
        }

    return render_template(
        "admin.html",
        users=users,
        levels=levels,
        attempts=attempts,
        user_stats=user_stats,
    )


@admin_bp.route("/level", methods=["POST"])
@login_required
@admin_required
def create_level():
    code = request.form["code"].strip().upper()
    name = request.form["name"].strip()
    description = request.form.get("description", "").strip()

    if Level.query.filter_by(code=code).first():
        flash(f"Level '{code}' already exists.", "warning")
        return redirect(url_for("admin.panel"))

    db.session.add(Level(code=code, name=name, description=description))
    db.session.commit()
    flash(f"Level '{code}' created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/topic", methods=["POST"])
@login_required
@admin_required
def create_topic():
    db.session.add(
        Topic(
            level_id=int(request.form["level_id"]),
            title=request.form["title"].strip(),
            theory=request.form["theory"].strip(),
        )
    )
    db.session.commit()
    flash("Topic created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/question", methods=["POST"])
@login_required
@admin_required
def create_question():
    db.session.add(
        Question(
            topic_id=int(request.form["topic_id"]),
            prompt=request.form["prompt"].strip(),
            option_a=request.form["option_a"].strip(),
            option_b=request.form["option_b"].strip(),
            option_c=request.form["option_c"].strip(),
            option_d=request.form["option_d"].strip(),
            correct_option=request.form["correct_option"].strip().upper(),
            explanation=request.form.get("explanation", "").strip(),
        )
    )
    db.session.commit()
    flash("Question created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/user", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = _normalize_username(request.form.get("username"))
    full_name = (request.form.get("full_name") or "").strip()
    password = request.form.get("password") or ""
    role = _validate_role(request.form.get("role"))

    if not username:
        flash("Username is required.", "danger")
        return redirect(url_for("admin.panel"))

    if not full_name:
        flash("Full name is required.", "danger")
        return redirect(url_for("admin.panel"))

    if role is None:
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.panel"))

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return redirect(url_for("admin.panel"))

    if User.query.filter(func.lower(User.username) == username.lower()).first():
        flash(f"Username '{username}' already exists.", "warning")
        return redirect(url_for("admin.panel"))

    user = User(username=username, full_name=full_name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"User '{username}' created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        username = _normalize_username(request.form.get("username"))
        full_name = (request.form.get("full_name") or "").strip()
        role = _validate_role(request.form.get("role"))
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not username:
            flash("Username is required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if len(username) > 80:
            flash("Username cannot exceed 80 characters.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if not full_name:
            flash("Full name is required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if len(full_name) > 120:
            flash("Full name cannot exceed 120 characters.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if role is None:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        duplicate = (
            User.query
            .filter(
                func.lower(User.username) == username.lower(),
                User.id != user.id,
            )
            .first()
        )
        if duplicate:
            flash(f"Username '{username}' is already used by another account.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        # The administrator currently logged in must not accidentally remove
        # their own administrator privileges and lock themselves out.
        if user.id == current_user.id and role != "admin":
            flash("You cannot remove administrator access from your own active account.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if new_password:
            if len(new_password) < 8:
                flash("The new password must contain at least 8 characters.", "danger")
                return redirect(url_for("admin.edit_user", user_id=user.id))
            if new_password != confirm_password:
                flash("The password confirmation does not match.", "danger")
                return redirect(url_for("admin.edit_user", user_id=user.id))

        old_username = user.username

        user.username = username
        user.full_name = full_name
        user.role = role

        if new_password:
            user.set_password(new_password)

        db.session.commit()

        if new_password:
            flash(
                f"User '{username}' updated and password reset successfully.",
                "success",
            )
        elif old_username != username:
            flash(
                f"User '{old_username}' updated. New username: '{username}'.",
                "success",
            )
        else:
            flash(f"User '{username}' updated successfully.", "success")

        return redirect(url_for("admin.panel"))

    stats = {
        "practice_attempts": Attempt.query.filter_by(user_id=user.id).count(),
        "assessment_attempts": AssessmentAttempt.query.filter_by(user_id=user.id).count(),
        "completed_lessons": TopicProgress.query.filter_by(
            user_id=user.id,
            completed=True,
        ).count(),
    }

    return render_template(
        "admin_user_edit.html",
        edited_user=user,
        stats=stats,
    )


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own active account.", "danger")
        return redirect(url_for("admin.panel"))

    practice_count = Attempt.query.filter_by(user_id=user.id).count()
    assessment_count = AssessmentAttempt.query.filter_by(user_id=user.id).count()
    progress_count = TopicProgress.query.filter_by(user_id=user.id).count()

    if practice_count or assessment_count or progress_count:
        flash(
            (
                f"User '{user.username}' has learning history and was not deleted. "
                "Edit the account instead so progress and assessment records remain intact."
            ),
            "warning",
        )
        return redirect(url_for("admin.panel"))

    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("admin.panel"))
