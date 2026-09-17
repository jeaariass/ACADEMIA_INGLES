from collections import defaultdict
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    abort,
    jsonify,
    flash,
)
from flask_login import login_required, current_user

from . import db
from .models import (
    Level,
    Topic,
    Assessment,
    AssessmentQuestion,
    AssessmentAttempt,
    AssessmentAnswer,
    TopicProgress,
)
from .progress import assessment_access

assessment_bp = Blueprint(
    "assessment",
    __name__,
    url_prefix="/assessments",
)

SECTION_ORDER = [
    "grammar",
    "vocabulary",
    "reading",
    "listening",
    "integrated",
]

SECTION_LABELS = {
    "grammar": "Grammar & Use of English",
    "vocabulary": "Vocabulary",
    "reading": "Reading",
    "listening": "Listening",
    "integrated": "Integrated Use of English",
}

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
DIAGNOSTIC_START_LEVEL = "B1"
DIAGNOSTIC_ADVANCE_THRESHOLD = 75.0
DIAGNOSTIC_CONFIRM_THRESHOLD = 60.0

FINAL_START_LEVEL = "A1"
FINAL_LEVEL_THRESHOLD = 70.0
FINAL_FOUNDATION_THRESHOLD = 60.0


def get_owned_attempt(attempt_id):
    attempt = AssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return attempt


def build_sections_from_links(links):
    grouped = {key: [] for key in SECTION_ORDER}
    for link in links:
        grouped.setdefault(link.section, []).append(link)

    return [
        {
            "key": key,
            "label": SECTION_LABELS.get(key, key.title()),
            "links": sorted(grouped.get(key, []), key=lambda x: x.sort_order),
        }
        for key in SECTION_ORDER
        if grouped.get(key)
    ]


def build_sections(assessment):
    return build_sections_from_links(assessment.question_links)


def _level_index(code):
    return LEVEL_ORDER.index(code)


def _higher_level(code):
    idx = _level_index(code)
    return LEVEL_ORDER[idx + 1] if idx < len(LEVEL_ORDER) - 1 else None


def _lower_level(code):
    idx = _level_index(code)
    return LEVEL_ORDER[idx - 1] if idx > 0 else None


def diagnostic_links_for_level(assessment, level_code):
    links = []
    for link in assessment.question_links:
        topic = link.question.topic
        if topic and topic.level and topic.level.code == level_code:
            links.append(link)
    return sorted(links, key=lambda x: x.sort_order)


def diagnostic_bank_summary(assessment):
    summary = []
    for code in LEVEL_ORDER:
        links = diagnostic_links_for_level(assessment, code)
        if links:
            summary.append({"code": code, "count": len(links)})
    return summary



def final_links_for_level(assessment, level_code):
    links = []
    for link in assessment.question_links:
        topic = link.question.topic
        if topic and topic.level and topic.level.code == level_code:
            links.append(link)
    return sorted(links, key=lambda x: x.sort_order)


def final_bank_summary(assessment):
    summary = []
    for code in LEVEL_ORDER:
        links = final_links_for_level(assessment, code)
        if links:
            summary.append({"code": code, "count": len(links)})
    return summary


def _estimate_final_level(stage_scores):
    # Version 1 platform heuristic:
    # - a candidate level needs >= 70% in its own block;
    # - every lower block must be >= 60%;
    # - A1 is the platform floor and C2 the ceiling.
    estimated = "A1"
    for idx, code in enumerate(LEVEL_ORDER):
        current = stage_scores.get(code, {})
        if current.get("percentage", 0.0) < FINAL_LEVEL_THRESHOLD:
            continue
        lower_codes = LEVEL_ORDER[:idx]
        if all(
            stage_scores.get(lower, {}).get("percentage", 0.0)
            >= FINAL_FOUNDATION_THRESHOLD
            for lower in lower_codes
        ):
            estimated = code
    return estimated


def _complete_final(attempt):
    linked_ids = {link.question_id for link in attempt.assessment.question_links}
    completed_answers = [
        answer for answer in attempt.answers
        if answer.question_id in linked_ids and answer.selected_option is not None
    ]
    attempt.score = sum(1 for answer in completed_answers if answer.is_correct)
    attempt.total = len(completed_answers)
    attempt.percentage = (
        round((attempt.score / attempt.total) * 100, 1)
        if attempt.total else 0.0
    )

    profile = dict(attempt.result_profile or {})
    stage_scores = dict(profile.get("stage_scores") or {})
    attempt.estimated_level = _estimate_final_level(stage_scores)
    attempt.completed_at = datetime.utcnow()
    attempt.status = "completed"
    attempt.current_stage = None


def take_final(attempt):
    level_code = attempt.current_stage or FINAL_START_LEVEL
    stage_links = final_links_for_level(attempt.assessment, level_code)
    if not stage_links:
        abort(500, description=f"No final-assessment questions configured for {level_code}.")

    if request.method == "POST":
        missing = []
        stage_score = 0

        for link in stage_links:
            question = link.question
            selected = request.form.get(f"q_{question.id}", "").strip().upper()
            if selected not in {"A", "B", "C", "D"}:
                missing.append(question.id)
                continue

            answer = _upsert_diagnostic_answer(attempt, question, selected)
            if answer.is_correct:
                stage_score += 1

        if missing:
            db.session.rollback()
            flash("Please answer every question in this stage before continuing.", "warning")
            return redirect(url_for("assessment.take", attempt_id=attempt.id))

        stage_total = len(stage_links)
        stage_percentage = round((stage_score / stage_total) * 100, 1)

        path = list(attempt.diagnostic_path or [])
        if level_code not in path:
            path.append(level_code)
        attempt.diagnostic_path = path

        profile = dict(attempt.result_profile or {})
        stage_scores = dict(profile.get("stage_scores") or {})
        stage_scores[level_code] = {
            "correct": stage_score,
            "total": stage_total,
            "percentage": stage_percentage,
        }
        profile["stage_scores"] = stage_scores
        attempt.result_profile = profile

        next_level = _higher_level(level_code)
        if next_level:
            attempt.current_stage = next_level
            db.session.commit()
            return redirect(url_for("assessment.take", attempt_id=attempt.id))

        _complete_final(attempt)
        db.session.commit()
        return redirect(url_for("assessment.result", attempt_id=attempt.id))

    path = list(attempt.diagnostic_path or [])
    stage_number = len(path) + 1
    sections = build_sections_from_links(stage_links)
    completed_questions = sum(
        stat.get("total", 0)
        for stat in (attempt.result_profile or {}).get("stage_scores", {}).values()
    )

    return render_template(
        "final_take.html",
        attempt=attempt,
        assessment=attempt.assessment,
        sections=sections,
        level_code=level_code,
        stage_number=stage_number,
        completed_questions=completed_questions,
        current_stage_questions=len(stage_links),
        path=path,
        all_levels=LEVEL_ORDER,
    )


def calculate_final_profile(attempt):
    linked_ids = {link.question_id for link in attempt.assessment.question_links}
    answers = [
        answer for answer in attempt.answers
        if answer.question_id in linked_ids and answer.selected_option is not None
    ]

    skill_data = defaultdict(lambda: {"correct": 0, "total": 0})
    topic_data = defaultdict(lambda: {"correct": 0, "total": 0, "topic": None})
    level_data = defaultdict(lambda: {"correct": 0, "total": 0})

    for answer in answers:
        q = answer.question
        skill = q.skill if q.skill in {"grammar", "vocabulary", "reading", "listening"} else "grammar"
        skill_data[skill]["total"] += 1
        if answer.is_correct:
            skill_data[skill]["correct"] += 1

        if q.topic:
            entry = topic_data[q.topic_id]
            entry["topic"] = q.topic
            entry["total"] += 1
            level_code = q.topic.level.code
            level_data[level_code]["total"] += 1
            if answer.is_correct:
                entry["correct"] += 1
                level_data[level_code]["correct"] += 1

    skill_stats = []
    for skill in ["grammar", "vocabulary", "reading", "listening"]:
        data = skill_data.get(skill, {"correct": 0, "total": 0})
        total = data["total"]
        pct = round((data["correct"] / total) * 100, 1) if total else 0.0
        skill_stats.append({
            "key": skill,
            "label": SECTION_LABELS.get(skill, skill.title()),
            "correct": data["correct"],
            "total": total,
            "percentage": pct,
        })

    stage_scores = dict((attempt.result_profile or {}).get("stage_scores") or {})
    level_stats = []
    for code in LEVEL_ORDER:
        stat = stage_scores.get(code)
        if stat:
            level_stats.append({"code": code, **stat})

    topic_stats = []
    for entry in topic_data.values():
        total = entry["total"]
        pct = round((entry["correct"] / total) * 100, 1) if total else 0.0
        topic_stats.append({
            "topic": entry["topic"],
            "correct": entry["correct"],
            "total": total,
            "percentage": pct,
        })

    estimated_code = attempt.estimated_level or "A1"
    estimated_index = _level_index(estimated_code)

    # Questions above the estimated level are useful for level estimation but
    # are not treated as "weaknesses" the learner must already have mastered.
    eligible_review = [
        item for item in topic_stats
        if _level_index(item["topic"].level.code) <= estimated_index
        and item["percentage"] < 70
    ]
    recommendations = sorted(
        eligible_review,
        key=lambda item: (
            0 if item["topic"].level.code == estimated_code else 1,
            item["percentage"],
            -_level_index(item["topic"].level.code),
            item["topic"].sort_order,
        ),
    )[:8]

    strengths = sorted(
        [
            item for item in topic_stats
            if _level_index(item["topic"].level.code) <= estimated_index
            and item["percentage"] >= 80
        ],
        key=lambda item: (
            -_level_index(item["topic"].level.code),
            -item["percentage"],
            item["topic"].sort_order,
        ),
    )[:6]

    estimated_level = Level.query.filter_by(code=estimated_code).first()
    suggested_topic = next(
        (
            item["topic"] for item in recommendations
            if item["topic"].level.code == estimated_code
        ),
        None,
    )
    if suggested_topic is None and estimated_level:
        suggested_topic = (
            Topic.query
            .filter_by(level_id=estimated_level.id, is_published=True)
            .order_by(Topic.sort_order.asc(), Topic.id.asc())
            .first()
        )

    # Latest initial diagnostic completed before this final attempt.
    diagnostic = (
        Assessment.query
        .filter_by(assessment_type="diagnostic", is_published=True)
        .order_by(Assessment.id.asc())
        .first()
    )
    initial_attempt = None
    initial_profile = None
    if diagnostic:
        query = (
            AssessmentAttempt.query
            .filter_by(
                user_id=attempt.user_id,
                assessment_id=diagnostic.id,
                status="completed",
            )
        )
        if attempt.completed_at:
            query = query.filter(AssessmentAttempt.completed_at <= attempt.completed_at)
        initial_attempt = query.order_by(AssessmentAttempt.completed_at.desc()).first()
        if initial_attempt:
            initial_profile = calculate_diagnostic_profile(initial_attempt)

    growth = None
    if initial_attempt and initial_profile:
        initial_skills = {
            item["key"]: item["percentage"]
            for item in initial_profile["skill_stats"]
        }
        final_skills = {
            item["key"]: item["percentage"]
            for item in skill_stats
        }
        rows = []
        for skill in ["grammar", "vocabulary", "reading", "listening"]:
            before = initial_skills.get(skill, 0.0)
            after = final_skills.get(skill, 0.0)
            rows.append({
                "key": skill,
                "label": SECTION_LABELS.get(skill, skill.title()),
                "initial": before,
                "final": after,
                "delta": round(after - before, 1),
            })

        initial_code = initial_attempt.estimated_level or "A1"
        growth = {
            "initial_attempt": initial_attempt,
            "initial_level": initial_code,
            "final_level": estimated_code,
            "level_delta": _level_index(estimated_code) - _level_index(initial_code),
            "skills": rows,
        }

    published_topics = Topic.query.filter_by(is_published=True).all()
    topic_ids = [topic.id for topic in published_topics]
    completed_lessons = 0
    if topic_ids:
        completed_lessons = (
            TopicProgress.query
            .filter(
                TopicProgress.user_id == attempt.user_id,
                TopicProgress.topic_id.in_(topic_ids),
                TopicProgress.completed.is_(True),
            )
            .count()
        )

    level_assessment_rows = []
    level_assessments = (
        Assessment.query
        .filter_by(assessment_type="level", is_published=True)
        .all()
    )
    for item in level_assessments:
        latest = (
            AssessmentAttempt.query
            .filter_by(
                user_id=attempt.user_id,
                assessment_id=item.id,
                status="completed",
            )
            .order_by(AssessmentAttempt.completed_at.desc())
            .first()
        )
        if latest and item.level:
            level_assessment_rows.append({
                "code": item.level.code,
                "percentage": latest.percentage,
            })
    level_assessment_rows.sort(
        key=lambda item: _level_index(item["code"])
    )

    return {
        "skill_stats": skill_stats,
        "level_stats": level_stats,
        "topic_stats": topic_stats,
        "recommendations": recommendations,
        "strengths": strengths,
        "suggested_topic": suggested_topic,
        "estimated_level": estimated_level,
        "growth": growth,
        "journey": {
            "completed_lessons": completed_lessons,
            "total_lessons": len(published_topics),
            "level_assessments": level_assessment_rows,
        },
    }


def calculate_result(attempt):
    links = attempt.assessment.question_links
    answers = {
        answer.question_id: answer
        for answer in attempt.answers
        if answer.selected_option is not None
    }

    section_stats = {}
    for section in SECTION_ORDER:
        section_links = [link for link in links if link.section == section]
        if not section_links:
            continue
        correct = sum(
            1 for link in section_links
            if answers.get(link.question_id) and answers[link.question_id].is_correct
        )
        total = len(section_links)
        section_stats[section] = {
            "label": SECTION_LABELS.get(section, section.title()),
            "correct": correct,
            "total": total,
            "percentage": round((correct / total) * 100, 1) if total else 0,
        }

    topic_data = defaultdict(lambda: {"correct": 0, "total": 0, "topic": None})
    for link in links:
        q = link.question
        if not q.topic:
            continue
        entry = topic_data[q.topic_id]
        entry["topic"] = q.topic
        entry["total"] += 1
        answer = answers.get(q.id)
        if answer and answer.is_correct:
            entry["correct"] += 1

    topic_stats = []
    for entry in topic_data.values():
        total = entry["total"]
        pct = round((entry["correct"] / total) * 100, 1) if total else 0
        topic_stats.append({
            "topic": entry["topic"],
            "correct": entry["correct"],
            "total": total,
            "percentage": pct,
        })

    topic_stats.sort(key=lambda x: (x["percentage"], x["topic"].sort_order))
    recommendations = [item for item in topic_stats if item["percentage"] < 70][:5]
    strengths = sorted(
        [item for item in topic_stats if item["percentage"] >= 80],
        key=lambda x: (-x["percentage"], x["topic"].sort_order),
    )[:5]
    return section_stats, topic_stats, recommendations, strengths


def _upsert_diagnostic_answer(attempt, question, selected):
    answer = AssessmentAnswer.query.filter_by(
        assessment_attempt_id=attempt.id,
        question_id=question.id,
    ).first()
    if not answer:
        answer = AssessmentAnswer(
            assessment_attempt_id=attempt.id,
            question_id=question.id,
            audio_plays=0,
        )
        db.session.add(answer)
    answer.selected_option = selected
    answer.is_correct = selected == question.correct_option
    return answer


def _diagnostic_next_step(attempt, level_code, percentage):
    direction = attempt.diagnostic_direction

    # Initial B1 screen. A borderline B1 result is confirmed with A2 so that
    # the diagnostic never ends after only one 18-item stage.
    if direction is None:
        if percentage >= DIAGNOSTIC_ADVANCE_THRESHOLD:
            return _higher_level(level_code), "up", None
        if percentage >= DIAGNOSTIC_CONFIRM_THRESHOLD:
            return "A2", "confirm_b1", None
        return "A2", "down", None

    if direction == "confirm_b1":
        if percentage >= DIAGNOSTIC_ADVANCE_THRESHOLD:
            return None, direction, "B1"
        if percentage >= DIAGNOSTIC_CONFIRM_THRESHOLD:
            return None, direction, "A2"
        return "A1", "down", None

    if direction == "up":
        if percentage >= DIAGNOSTIC_ADVANCE_THRESHOLD:
            higher = _higher_level(level_code)
            if higher:
                return higher, direction, None
            return None, direction, "C2"
        if percentage >= DIAGNOSTIC_CONFIRM_THRESHOLD:
            return None, direction, level_code
        return None, direction, _lower_level(level_code) or "A1"

    # Downward confirmation path.
    if percentage >= DIAGNOSTIC_CONFIRM_THRESHOLD:
        return None, direction, level_code
    lower = _lower_level(level_code)
    if lower:
        return lower, direction, None
    return None, direction, "A1"


def _complete_diagnostic(attempt, estimated_level):
    linked_ids = {link.question_id for link in attempt.assessment.question_links}
    completed_answers = [
        answer for answer in attempt.answers
        if answer.question_id in linked_ids and answer.selected_option is not None
    ]
    attempt.score = sum(1 for answer in completed_answers if answer.is_correct)
    attempt.total = len(completed_answers)
    attempt.percentage = (
        round((attempt.score / attempt.total) * 100, 1)
        if attempt.total else 0.0
    )
    attempt.estimated_level = estimated_level
    attempt.completed_at = datetime.utcnow()
    attempt.status = "completed"
    attempt.current_stage = None


def take_diagnostic(attempt):
    level_code = attempt.current_stage or DIAGNOSTIC_START_LEVEL
    stage_links = diagnostic_links_for_level(attempt.assessment, level_code)
    if not stage_links:
        abort(500, description=f"No diagnostic questions configured for {level_code}.")

    if request.method == "POST":
        missing = []
        stage_score = 0
        for link in stage_links:
            question = link.question
            selected = request.form.get(f"q_{question.id}", "").strip().upper()
            if selected not in {"A", "B", "C", "D"}:
                missing.append(question.id)
                continue
            answer = _upsert_diagnostic_answer(attempt, question, selected)
            if answer.is_correct:
                stage_score += 1

        if missing:
            db.session.rollback()
            flash("Please answer every question in this stage before continuing.", "warning")
            return redirect(url_for("assessment.take", attempt_id=attempt.id))

        stage_total = len(stage_links)
        stage_percentage = round((stage_score / stage_total) * 100, 1)

        path = list(attempt.diagnostic_path or [])
        if level_code not in path:
            path.append(level_code)
        attempt.diagnostic_path = path

        profile = dict(attempt.result_profile or {})
        stage_scores = dict(profile.get("stage_scores") or {})
        stage_scores[level_code] = {
            "correct": stage_score,
            "total": stage_total,
            "percentage": stage_percentage,
        }
        profile["stage_scores"] = stage_scores
        attempt.result_profile = profile

        next_level, next_direction, estimated = _diagnostic_next_step(
            attempt, level_code, stage_percentage
        )
        attempt.diagnostic_direction = next_direction

        if next_level:
            attempt.current_stage = next_level
            db.session.commit()
            return redirect(url_for("assessment.take", attempt_id=attempt.id))

        _complete_diagnostic(attempt, estimated or level_code)
        db.session.commit()
        return redirect(url_for("assessment.result", attempt_id=attempt.id))

    path = list(attempt.diagnostic_path or [])
    stage_number = len(path) + 1
    sections = build_sections_from_links(stage_links)
    completed_questions = sum(
        stat.get("total", 0)
        for stat in (attempt.result_profile or {}).get("stage_scores", {}).values()
    )

    return render_template(
        "diagnostic_take.html",
        attempt=attempt,
        assessment=attempt.assessment,
        sections=sections,
        level_code=level_code,
        stage_number=stage_number,
        completed_questions=completed_questions,
        current_stage_questions=len(stage_links),
        path=path,
    )


def calculate_diagnostic_profile(attempt):
    linked_ids = {link.question_id for link in attempt.assessment.question_links}
    answers = [
        answer for answer in attempt.answers
        if answer.question_id in linked_ids and answer.selected_option is not None
    ]

    skill_data = defaultdict(lambda: {"correct": 0, "total": 0})
    topic_data = defaultdict(lambda: {"correct": 0, "total": 0, "topic": None})

    for answer in answers:
        question = answer.question
        skill = question.skill if question.skill in {"grammar", "vocabulary", "reading", "listening"} else "grammar"
        skill_data[skill]["total"] += 1
        if answer.is_correct:
            skill_data[skill]["correct"] += 1

        if question.topic:
            entry = topic_data[question.topic_id]
            entry["topic"] = question.topic
            entry["total"] += 1
            if answer.is_correct:
                entry["correct"] += 1

    skill_stats = []
    for skill in ["grammar", "vocabulary", "reading", "listening"]:
        data = skill_data.get(skill, {"correct": 0, "total": 0})
        total = data["total"]
        pct = round((data["correct"] / total) * 100, 1) if total else 0.0
        skill_stats.append({
            "key": skill,
            "label": SECTION_LABELS.get(skill, skill.title()),
            "correct": data["correct"],
            "total": total,
            "percentage": pct,
        })

    topic_stats = []
    for entry in topic_data.values():
        total = entry["total"]
        pct = round((entry["correct"] / total) * 100, 1) if total else 0.0
        topic_stats.append({
            "topic": entry["topic"],
            "correct": entry["correct"],
            "total": total,
            "percentage": pct,
        })

    estimated_code = attempt.estimated_level or "A1"
    estimated_level = Level.query.filter_by(code=estimated_code).first()

    # Missed diagnostic items indicate areas worth reviewing; they are not
    # presented as psychometrically validated topic diagnoses.
    recommendations = sorted(
        [item for item in topic_stats if item["percentage"] < 70],
        key=lambda item: (
            0 if item["topic"].level.code == estimated_code else 1,
            item["percentage"],
            -item["total"],
            item["topic"].sort_order,
        ),
    )[:6]

    strengths = sorted(
        [item for item in topic_stats if item["percentage"] >= 80],
        key=lambda item: (-item["percentage"], -item["total"]),
    )[:5]

    suggested_topic = next(
        (
            item["topic"] for item in recommendations
            if item["topic"].level.code == estimated_code
        ),
        None,
    )
    if suggested_topic is None and estimated_level:
        suggested_topic = (
            Topic.query
            .filter_by(level_id=estimated_level.id, is_published=True)
            .order_by(Topic.sort_order.asc(), Topic.id.asc())
            .first()
        )

    stage_scores = (attempt.result_profile or {}).get("stage_scores", {})
    path = list(attempt.diagnostic_path or [])
    level_path = []
    for code in path:
        if code in stage_scores:
            level_path.append({"code": code, **stage_scores[code]})

    return {
        "skill_stats": skill_stats,
        "topic_stats": topic_stats,
        "recommendations": recommendations,
        "strengths": strengths,
        "suggested_topic": suggested_topic,
        "estimated_level": estimated_level,
        "level_path": level_path,
        "answered_count": len(answers),
    }


@assessment_bp.route("/")
@login_required
def index():
    assessments = (
        Assessment.query
        .filter_by(is_published=True)
        .order_by(Assessment.id.asc())
        .all()
    )
    assessment_cards = []
    for assessment in assessments:
        access = assessment_access(current_user, assessment)
        assessment_cards.append({
            "assessment": assessment,
            "unlocked": access["unlocked"],
            "reason": access["reason"],
            "progress": access["progress"],
        })
    return render_template("assessments.html", assessment_cards=assessment_cards)


@assessment_bp.route("/<string:code>")
@login_required
def intro(code):
    assessment = Assessment.query.filter_by(
        code=code.upper(), is_published=True
    ).first_or_404()
    access = assessment_access(current_user, assessment)
    if not access["unlocked"]:
        flash(access["reason"] or "This assessment is currently locked.", "warning")
        return redirect(url_for("assessment.index"))

    latest_attempt = (
        AssessmentAttempt.query
        .filter_by(
            user_id=current_user.id,
            assessment_id=assessment.id,
            status="completed",
        )
        .order_by(AssessmentAttempt.completed_at.desc())
        .first()
    )

    if assessment.assessment_type == "diagnostic":
        return render_template(
            "diagnostic_intro.html",
            assessment=assessment,
            bank_summary=diagnostic_bank_summary(assessment),
            bank_count=len(assessment.question_links),
            latest_attempt=latest_attempt,
        )

    if assessment.assessment_type == "final":
        return render_template(
            "final_intro.html",
            assessment=assessment,
            bank_summary=final_bank_summary(assessment),
            bank_count=len(assessment.question_links),
            latest_attempt=latest_attempt,
            course_progress=access["progress"],
        )

    return render_template(
        "assessment_intro.html",
        assessment=assessment,
        sections=build_sections(assessment),
        question_count=len(assessment.question_links),
        latest_attempt=latest_attempt,
    )


@assessment_bp.route("/<string:code>/start", methods=["POST"])
@login_required
def start(code):
    assessment = Assessment.query.filter_by(
        code=code.upper(), is_published=True
    ).first_or_404()
    access = assessment_access(current_user, assessment)
    if not access["unlocked"]:
        flash(access["reason"] or "This assessment is currently locked.", "warning")
        return redirect(url_for("assessment.index"))

    is_diagnostic = assessment.assessment_type == "diagnostic" and assessment.is_adaptive
    is_final = assessment.assessment_type == "final"
    staged_assessment = is_diagnostic or is_final

    attempt = AssessmentAttempt(
        user_id=current_user.id,
        assessment_id=assessment.id,
        score=0,
        total=0 if staged_assessment else len(assessment.question_links),
        percentage=0.0,
        status="in_progress",
        current_stage=(
            DIAGNOSTIC_START_LEVEL if is_diagnostic
            else (FINAL_START_LEVEL if is_final else None)
        ),
        diagnostic_direction=None,
        diagnostic_path=[] if staged_assessment else None,
        result_profile={"stage_scores": {}} if staged_assessment else None,
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("assessment.take", attempt_id=attempt.id))


@assessment_bp.route("/attempt/<int:attempt_id>", methods=["GET", "POST"])
@login_required
def take(attempt_id):
    attempt = get_owned_attempt(attempt_id)
    if attempt.status == "completed":
        return redirect(url_for("assessment.result", attempt_id=attempt.id))

    if attempt.assessment.assessment_type == "diagnostic" and attempt.assessment.is_adaptive:
        return take_diagnostic(attempt)

    if attempt.assessment.assessment_type == "final":
        return take_final(attempt)

    if request.method == "POST":
        score = 0
        for link in attempt.assessment.question_links:
            q = link.question
            selected = request.form.get(f"q_{q.id}", "")
            answer = AssessmentAnswer.query.filter_by(
                assessment_attempt_id=attempt.id,
                question_id=q.id,
            ).first()
            if not answer:
                answer = AssessmentAnswer(
                    assessment_attempt_id=attempt.id,
                    question_id=q.id,
                    audio_plays=0,
                )
                db.session.add(answer)
            answer.selected_option = selected or None
            answer.is_correct = bool(selected) and selected == q.correct_option
            if answer.is_correct:
                score += 1

        attempt.score = score
        attempt.total = len(attempt.assessment.question_links)
        attempt.percentage = round((score / attempt.total) * 100, 1) if attempt.total else 0.0
        attempt.completed_at = datetime.utcnow()
        attempt.status = "completed"

        if (
            attempt.assessment.assessment_type == "level"
            and attempt.assessment.level
            and attempt.assessment.passing_score is not None
            and attempt.percentage >= attempt.assessment.passing_score
        ):
            attempt.estimated_level = attempt.assessment.level.code
        else:
            attempt.estimated_level = None

        db.session.commit()
        return redirect(url_for("assessment.result", attempt_id=attempt.id))

    return render_template(
        "assessment_take.html",
        attempt=attempt,
        assessment=attempt.assessment,
        sections=build_sections(attempt.assessment),
    )


@assessment_bp.route(
    "/attempt/<int:attempt_id>/audio/<int:question_id>", methods=["POST"]
)
@login_required
def register_audio_play(attempt_id, question_id):
    attempt = get_owned_attempt(attempt_id)
    if attempt.status != "in_progress":
        return jsonify({"allowed": False, "remaining": 0}), 400

    link = AssessmentQuestion.query.filter_by(
        assessment_id=attempt.assessment_id,
        question_id=question_id,
    ).first()
    if not link:
        abort(404)

    q = link.question
    storage_question_id = q.id
    max_plays = q.max_audio_plays or 2

    if q.passage and q.passage.passage_type == "listening":
        linked_ids = {item.question_id for item in attempt.assessment.question_links}
        passage_question_ids = [
            pq.id for pq in q.passage.questions if pq.id in linked_ids
        ]
        if passage_question_ids:
            storage_question_id = min(passage_question_ids)
        max_plays = q.passage.max_audio_plays or 2

    answer = AssessmentAnswer.query.filter_by(
        assessment_attempt_id=attempt.id,
        question_id=storage_question_id,
    ).first()
    if not answer:
        answer = AssessmentAnswer(
            assessment_attempt_id=attempt.id,
            question_id=storage_question_id,
            audio_plays=0,
            selected_option=None,
            is_correct=False,
        )
        db.session.add(answer)
        db.session.flush()

    if answer.audio_plays >= max_plays:
        return jsonify({"allowed": False, "remaining": 0})

    answer.audio_plays += 1
    db.session.commit()
    return jsonify({
        "allowed": True,
        "remaining": max_plays - answer.audio_plays,
        "plays": answer.audio_plays,
    })


@assessment_bp.route("/attempt/<int:attempt_id>/result")
@login_required
def result(attempt_id):
    attempt = get_owned_attempt(attempt_id)
    if attempt.status != "completed":
        return redirect(url_for("assessment.take", attempt_id=attempt.id))

    if attempt.assessment.assessment_type == "diagnostic":
        profile = calculate_diagnostic_profile(attempt)
        return render_template(
            "diagnostic_result.html",
            attempt=attempt,
            assessment=attempt.assessment,
            profile=profile,
        )

    if attempt.assessment.assessment_type == "final":
        profile = calculate_final_profile(attempt)
        return render_template(
            "final_result.html",
            attempt=attempt,
            assessment=attempt.assessment,
            profile=profile,
        )

    section_stats, topic_stats, recommendations, strengths = calculate_result(attempt)
    return render_template(
        "assessment_result.html",
        attempt=attempt,
        assessment=attempt.assessment,
        section_stats=section_stats,
        topic_stats=topic_stats,
        recommendations=recommendations,
        strengths=strengths,
        threshold=attempt.assessment.passing_score,
    )
