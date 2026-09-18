from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from . import db
from .models import Level, Topic, Question, Passage, Attempt, Answer, Assessment
from .progress import (
    update_topic_progress,
    get_level_progress,
    get_level_assessment,
)
from .learning_plan import ensure_learning_plan, get_learning_plan_summary
from .insights import get_student_insights

main_bp = Blueprint("main", __name__)


def get_next_topic(topic):
    return (
        Topic.query
        .filter(
            Topic.level_id == topic.level_id,
            Topic.is_published.is_(True),
            Topic.sort_order > topic.sort_order,
        )
        .order_by(Topic.sort_order.asc(), Topic.id.asc())
        .first()
    )


@main_bp.route("/")
def index():
    return redirect(
        url_for("main.dashboard")
        if current_user.is_authenticated
        else url_for("auth.login")
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    if ensure_learning_plan(current_user.id):
        db.session.commit()

    levels = Level.query.order_by(Level.sort_order, Level.code).all()
    plan_summary = get_learning_plan_summary(current_user.id)

    level_cards = []
    for level in levels:
        progress = get_level_progress(current_user.id, level)
        level_cards.append({
            "level": level,
            "progress": progress,
            "assessment": get_level_assessment(level),
        })

    insights = get_student_insights(current_user.id)

    attempts = (
        Attempt.query
        .filter_by(user_id=current_user.id)
        .order_by(Attempt.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        levels=levels,
        level_cards=level_cards,
        attempts=attempts,
        plan_summary=plan_summary,
        insights=insights,
    )


@main_bp.route("/learning-path")
@login_required
def learning_path():
    if ensure_learning_plan(current_user.id):
        db.session.commit()

    plan_summary = get_learning_plan_summary(current_user.id)
    diagnostic = (
        Assessment.query
        .filter_by(assessment_type="diagnostic", is_published=True)
        .order_by(Assessment.id.asc())
        .first()
    )
    return render_template(
        "learning_path.html",
        plan_summary=plan_summary,
        diagnostic=diagnostic,
    )


@main_bp.route("/topic/<int:topic_id>")
@login_required
def topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    next_topic = get_next_topic(topic)
    return render_template(
        "topic.html",
        topic=topic,
        next_topic=next_topic,
    )


@main_bp.route("/test/<int:topic_id>", methods=["GET", "POST"])
@login_required
def test(topic_id):
    topic = Topic.query.get_or_404(topic_id)

    questions = (
        Question.query
        .filter_by(topic_id=topic.id, is_active=True)
        .order_by(Question.sort_order.asc(), Question.id.asc())
        .all()
    )

    if request.method == "POST":
        score = 0

        attempt = Attempt(
            user_id=current_user.id,
            topic_id=topic.id,
            score=0,
            total=len(questions),
        )
        db.session.add(attempt)
        db.session.flush()

        for q in questions:
            selected = request.form.get(f"q_{q.id}", "")
            is_correct = selected == q.correct_option
            score += 1 if is_correct else 0

            db.session.add(
                Answer(
                    attempt_id=attempt.id,
                    question_id=q.id,
                    selected_option=selected,
                    is_correct=is_correct,
                )
            )

        attempt.score = score
        update_topic_progress(
            user_id=current_user.id,
            topic=topic,
            attempt=attempt,
        )

        db.session.commit()
        return redirect(url_for("main.result", attempt_id=attempt.id))

    standalone_questions = [q for q in questions if q.passage_id is None]

    passages = (
        Passage.query
        .filter_by(topic_id=topic.id, is_active=True)
        .order_by(Passage.sort_order.asc(), Passage.id.asc())
        .all()
    )

    return render_template(
        "test.html",
        topic=topic,
        questions=questions,
        standalone_questions=standalone_questions,
        passages=passages,
    )


@main_bp.route("/result/<int:attempt_id>")
@login_required
def result(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for("main.dashboard"))

    progress = get_level_progress(attempt.user_id, attempt.topic.level)
    next_topic = progress["next_topic"] if progress["personalized"] else get_next_topic(attempt.topic)
    level_assessment = None

    if progress["is_complete"]:
        level_assessment = get_level_assessment(attempt.topic.level)

    return render_template(
        "result.html",
        attempt=attempt,
        next_topic=next_topic,
        level_assessment=level_assessment,
    )


@main_bp.route("/ranking")
@login_required
def ranking():
    attempts = Attempt.query.order_by(Attempt.created_at.desc()).all()
    return render_template("ranking.html", attempts=attempts)
