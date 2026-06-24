from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import User, Level, Topic, Question, Attempt

admin_bp = Blueprint("admin", __name__)

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acceso exclusivo para administración.", "warning")
            return redirect(url_for("main.dashboard"))
        return func(*args, **kwargs)
    return wrapper

@admin_bp.route("/")
@login_required
@admin_required
def panel():
    return render_template("admin.html", users=User.query.all(), levels=Level.query.order_by(Level.code).all(), attempts=Attempt.query.order_by(Attempt.created_at.desc()).limit(20).all())

@admin_bp.route("/level", methods=["POST"])
@login_required
@admin_required
def create_level():
    db.session.add(Level(code=request.form["code"].strip().upper(), name=request.form["name"].strip(), description=request.form.get("description", "")))
    db.session.commit()
    return redirect(url_for("admin.panel"))

@admin_bp.route("/topic", methods=["POST"])
@login_required
@admin_required
def create_topic():
    db.session.add(Topic(level_id=int(request.form["level_id"]), title=request.form["title"].strip(), theory=request.form["theory"].strip()))
    db.session.commit()
    return redirect(url_for("admin.panel"))

@admin_bp.route("/question", methods=["POST"])
@login_required
@admin_required
def create_question():
    db.session.add(Question(topic_id=int(request.form["topic_id"]), prompt=request.form["prompt"].strip(), option_a=request.form["option_a"].strip(), option_b=request.form["option_b"].strip(), option_c=request.form["option_c"].strip(), option_d=request.form["option_d"].strip(), correct_option=request.form["correct_option"].strip().upper(), explanation=request.form.get("explanation", "")))
    db.session.commit()
    return redirect(url_for("admin.panel"))

@admin_bp.route("/user", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form["username"].strip()
    if User.query.filter_by(username=username).first():
        flash(f"Usuario '{username}' ya existe.", "warning")
        return redirect(url_for("admin.panel"))
    u = User(username=username, full_name=request.form["full_name"].strip(), role=request.form.get("role", "student"))
    u.set_password(request.form["password"])
    db.session.add(u)
    db.session.commit()
    flash(f"Usuario '{username}' creado.", "success")
    return redirect(url_for("admin.panel"))

@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("No puedes eliminar tu propia cuenta.", "danger")
        return redirect(url_for("admin.panel"))
    db.session.delete(u)
    db.session.commit()
    flash(f"Usuario '{u.username}' eliminado.", "success")
    return redirect(url_for("admin.panel"))
