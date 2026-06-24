from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from . import db
from .models import Level, Topic, Question, Attempt, Answer

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard") if current_user.is_authenticated else url_for("auth.login"))

@main_bp.route("/dashboard")
@login_required
def dashboard():
    levels = Level.query.order_by(Level.code).all()
    attempts = Attempt.query.filter_by(user_id=current_user.id).order_by(Attempt.created_at.desc()).limit(5).all()
    return render_template("dashboard.html", levels=levels, attempts=attempts)

@main_bp.route("/topic/<int:topic_id>")
@login_required
def topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    return render_template("topic.html", topic=topic)

@main_bp.route("/test/<int:topic_id>", methods=["GET", "POST"])
@login_required
def test(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    questions = Question.query.filter_by(topic_id=topic.id).all()
    if request.method == "POST":
        score = 0
        attempt = Attempt(user_id=current_user.id, topic_id=topic.id, score=0, total=len(questions))
        db.session.add(attempt)
        db.session.flush()
        for q in questions:
            selected = request.form.get(f"q_{q.id}", "")
            is_correct = selected == q.correct_option
            score += 1 if is_correct else 0
            db.session.add(Answer(attempt_id=attempt.id, question_id=q.id, selected_option=selected, is_correct=is_correct))
        attempt.score = score
        db.session.commit()
        return redirect(url_for("main.result", attempt_id=attempt.id))
    return render_template("test.html", topic=topic, questions=questions)

@main_bp.route("/result/<int:attempt_id>")
@login_required
def result(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)
    if attempt.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for("main.dashboard"))
    return render_template("result.html", attempt=attempt)

@main_bp.route("/ranking")
@login_required
def ranking():
    attempts = Attempt.query.order_by(Attempt.created_at.desc()).all()
    return render_template("ranking.html", attempts=attempts)
