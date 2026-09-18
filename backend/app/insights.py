from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from flask import Blueprint, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .adaptive_level import result_summary as adaptive_result_summary
from .learning_plan import ensure_learning_plan, get_learning_plan_summary, latest_completed_diagnostic
from .models import (
    Assessment,
    AssessmentAttempt,
    GameRun,
    ArcadeRun,
    SpeakingAttempt,
    WritingSubmission,
    Level,
    SavedVocabulary,
    Topic,
    TopicProgress,
    UserTopicPlan,
)
from .progress import get_level_assessment, get_level_progress


insights_bp = Blueprint("insights", __name__, url_prefix="/profile")

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
SKILL_ORDER = ["grammar", "vocabulary", "reading", "listening"]
SKILL_LABELS = {
    "grammar": "Grammar & Use of English",
    "vocabulary": "Vocabulary",
    "reading": "Reading",
    "listening": "Listening",
}


def _latest_completed_attempts_by_assessment(user_id):
    rows = (
        AssessmentAttempt.query
        .filter_by(user_id=user_id, status="completed")
        .order_by(
            AssessmentAttempt.completed_at.desc(),
            AssessmentAttempt.id.desc(),
        )
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault(row.assessment_id, row)
    return list(latest.values())


def _formal_skill_profile(user_id):
    """Aggregate latest evidence per assessment, not every historical retake.

    This prevents a learner who repeats one assessment many times from
    dominating the profile. Percentages remain descriptive item accuracy, not
    a psychometric trait score.
    """
    latest_attempts = _latest_completed_attempts_by_assessment(user_id)
    counts = defaultdict(lambda: {"correct": 0, "total": 0})
    source_count = 0

    for attempt in latest_attempts:
        # Ranking/practice attempts are not included here; only formal assessments.
        if not attempt.assessment:
            continue
        source_count += 1
        linked_ids = {link.question_id for link in attempt.assessment.question_links}
        for answer in attempt.answers:
            if answer.selected_option is None or answer.question_id not in linked_ids:
                continue
            question = answer.question
            if not question:
                continue
            skill = question.skill if question.skill in SKILL_ORDER else None
            if not skill:
                continue
            counts[skill]["total"] += 1
            if answer.is_correct:
                counts[skill]["correct"] += 1

    rows = []
    for skill in SKILL_ORDER:
        item = counts[skill]
        total = item["total"]
        percentage = round((item["correct"] / total) * 100, 1) if total else None
        rows.append({
            "key": skill,
            "label": SKILL_LABELS[skill],
            "correct": item["correct"],
            "total": total,
            "percentage": percentage,
        })

    evidenced = [row for row in rows if row["total"]]
    weak = sorted(
        [row for row in evidenced if row["percentage"] < 70 and row["total"] >= 2],
        key=lambda row: (row["percentage"], -row["total"]),
    )
    strong = sorted(
        [row for row in evidenced if row["percentage"] >= 80 and row["total"] >= 3],
        key=lambda row: (-row["percentage"], -row["total"]),
    )

    return {
        "rows": rows,
        "assessment_sources": source_count,
        "weak": weak,
        "strong": strong,
        "total_items": sum(row["total"] for row in rows),
    }


def _lesson_stats(user_id):
    topics = Topic.query.filter_by(is_published=True).all()
    topic_ids = [topic.id for topic in topics]
    progress_rows = (
        TopicProgress.query
        .filter(
            TopicProgress.user_id == user_id,
            TopicProgress.topic_id.in_(topic_ids),
        )
        .all()
        if topic_ids
        else []
    )
    completed_rows = [row for row in progress_rows if row.completed]
    completed = len(completed_rows)
    total = len(topics)
    percentage = round((completed / total) * 100, 1) if total else 0.0
    avg_best = (
        round(sum(row.best_percentage for row in completed_rows) / completed, 1)
        if completed
        else None
    )
    return {
        "completed": completed,
        "total": total,
        "percentage": percentage,
        "average_best_percentage": avg_best,
    }


def _path_focus(user_id):
    plan = get_learning_plan_summary(user_id)
    if not plan:
        return {"summary": None, "required_pending": [], "recommended_pending": []}

    completed_ids = {
        row.topic_id
        for row in TopicProgress.query.filter_by(user_id=user_id, completed=True).all()
    }
    rows = list(plan["rows"])
    required_pending = [
        row for row in rows
        if row.status == "required" and row.topic_id not in completed_ids
    ][:8]
    recommended_pending = [
        row for row in rows
        if row.status == "recommended" and row.topic_id not in completed_ids
    ][:8]
    return {
        "summary": plan,
        "required_pending": required_pending,
        "recommended_pending": recommended_pending,
    }


def _vocabulary_stats(user_id):
    now = datetime.utcnow()
    items = SavedVocabulary.query.filter_by(user_id=user_id).all()
    translated = [item for item in items if (item.translation or "").strip()]
    due = [item for item in translated if item.next_review_at and item.next_review_at <= now]
    mastered = [item for item in translated if (item.mastery_level or 0) >= 5]

    correct_reviews = sum(item.correct_reviews or 0 for item in items)
    incorrect_reviews = sum(item.incorrect_reviews or 0 for item in items)
    review_total = correct_reviews + incorrect_reviews
    review_accuracy = round((correct_reviews / review_total) * 100, 1) if review_total else None

    distribution = {level: 0 for level in range(0, 6)}
    for item in items:
        level = max(0, min(5, int(item.mastery_level or 0)))
        distribution[level] += 1

    next_due = min(
        (item.next_review_at for item in translated if item.next_review_at),
        default=None,
    )

    return {
        "saved": len(items),
        "translated": len(translated),
        "due": len(due),
        "mastered": len(mastered),
        "correct_reviews": correct_reviews,
        "incorrect_reviews": incorrect_reviews,
        "review_total": review_total,
        "review_accuracy": review_accuracy,
        "distribution": distribution,
        "next_due": next_due,
    }


def _game_stats(user_id):
    runs = (
        GameRun.query
        .filter_by(user_id=user_id)
        .order_by(GameRun.started_at.desc(), GameRun.id.desc())
        .all()
    )
    completed = [run for run in runs if run.status == "completed"]
    answered = sum(run.questions_answered or 0 for run in runs)
    correct = sum(run.correct_answers or 0 for run in runs)
    accuracy = round((correct / answered) * 100, 1) if answered else None
    best_score = max((run.score or 0 for run in runs), default=0)
    best_distance = max((run.distance or 0 for run in runs), default=0)
    highest_tier = max((run.difficulty_tier or 1 for run in completed), default=0)
    return {
        "runs": len(runs),
        "completed": len(completed),
        "answered": answered,
        "correct": correct,
        "accuracy": accuracy,
        "best_score": best_score,
        "best_distance": int(best_distance),
        "highest_completed_tier": highest_tier,
        "next_tier": min(12, len(completed) + 1),
        "recent": runs[:5],
    }



def _speaking_stats(user_id):
    rows = SpeakingAttempt.query.filter_by(user_id=user_id).order_by(SpeakingAttempt.created_at.desc()).all()
    closed = [r for r in rows if r.similarity_score is not None]
    avg_similarity = round(sum(r.similarity_score for r in closed) / len(closed), 1) if closed else None
    avg_wpm_rows = [r for r in rows if r.words_per_minute is not None]
    avg_wpm = round(sum(r.words_per_minute for r in avg_wpm_rows) / len(avg_wpm_rows), 1) if avg_wpm_rows else None
    return {
        "attempts": len(rows),
        "closed_attempts": len(closed),
        "avg_similarity": avg_similarity,
        "avg_wpm": avg_wpm,
        "latest": rows[:5],
    }


def _writing_stats(user_id):
    rows = WritingSubmission.query.filter_by(user_id=user_id).order_by(WritingSubmission.created_at.desc()).all()
    prompt_ids = {r.prompt_id for r in rows}
    latest_by_prompt = {}
    for row in rows:
        latest_by_prompt.setdefault(row.prompt_id, row)
    latest_rows = list(latest_by_prompt.values())
    avg_words = round(sum(r.word_count for r in latest_rows) / len(latest_rows), 1) if latest_rows else None
    avg_unique = round(sum(r.unique_word_ratio for r in latest_rows if r.unique_word_ratio is not None) / len([r for r in latest_rows if r.unique_word_ratio is not None]), 1) if any(r.unique_word_ratio is not None for r in latest_rows) else None
    return {
        "submissions": len(rows),
        "prompts": len(prompt_ids),
        "avg_words_latest": avg_words,
        "avg_unique_latest": avg_unique,
        "latest": rows[:5],
    }


def _arcade_stats(user_id):
    rows = ArcadeRun.query.filter_by(user_id=user_id).order_by(ArcadeRun.started_at.desc()).all()
    completed = [r for r in rows if r.status == "completed"]
    total_rounds = sum(r.rounds_total or 0 for r in completed)
    correct = sum(r.rounds_correct or 0 for r in completed)
    accuracy = round(correct / total_rounds * 100, 1) if total_rounds else None
    by_game = Counter(r.game_type for r in completed)
    favorite = by_game.most_common(1)[0][0] if by_game else None
    return {
        "completed": len(completed),
        "accuracy": accuracy,
        "best_score": max((r.score or 0 for r in completed), default=0),
        "favorite": favorite,
        "recent": rows[:5],
    }

def _assessment_stats(user_id):
    latest_attempts = _latest_completed_attempts_by_assessment(user_id)
    level_rows = []
    diagnostic = None
    final_attempt = None
    formal_completed = 0

    for attempt in latest_attempts:
        assessment = attempt.assessment
        if not assessment:
            continue
        formal_completed += 1
        if assessment.assessment_type == "diagnostic":
            if diagnostic is None or (attempt.completed_at or datetime.min) > (diagnostic.completed_at or datetime.min):
                diagnostic = attempt
        elif assessment.assessment_type == "level" and assessment.level:
            adaptive = None
            if (attempt.result_profile or {}).get("adaptive_level"):
                adaptive = adaptive_result_summary(attempt)
            level_rows.append({
                "level": assessment.level.code,
                "title": assessment.title,
                "percentage": attempt.percentage,
                "score": attempt.score,
                "total": attempt.total,
                "completed_at": attempt.completed_at,
                "adaptive": adaptive,
            })
        elif assessment.assessment_type == "final":
            final_attempt = attempt

    level_rows.sort(key=lambda row: LEVEL_ORDER.index(row["level"]) if row["level"] in LEVEL_ORDER else 999)
    latest_level = level_rows[-1] if level_rows else None

    return {
        "formal_completed": formal_completed,
        "diagnostic": diagnostic,
        "estimated_level": diagnostic.estimated_level if diagnostic else None,
        "levels": level_rows,
        "latest_level": latest_level,
        "final": final_attempt,
    }


def _recent_activity(user_id):
    events = []

    progress_rows = (
        TopicProgress.query
        .filter_by(user_id=user_id)
        .order_by(TopicProgress.last_practiced_at.desc())
        .limit(8)
        .all()
    )
    for row in progress_rows:
        if not row.last_practiced_at:
            continue
        events.append({
            "at": row.last_practiced_at,
            "kind": "lesson",
            "icon": "bi-journal-check",
            "title": row.topic.title,
            "detail": f"Best practice score {row.best_percentage}%",
            "url": url_for("main.topic", topic_id=row.topic_id),
        })

    assessment_rows = (
        AssessmentAttempt.query
        .filter_by(user_id=user_id, status="completed")
        .order_by(AssessmentAttempt.completed_at.desc())
        .limit(8)
        .all()
    )
    for row in assessment_rows:
        if not row.completed_at:
            continue
        label = "Diagnostic" if row.assessment.assessment_type == "diagnostic" else "Assessment"
        if row.assessment.assessment_type == "final":
            label = "Final assessment"
        events.append({
            "at": row.completed_at,
            "kind": "assessment",
            "icon": "bi-clipboard2-check",
            "title": row.assessment.title,
            "detail": f"{label} · {row.percentage}%",
            "url": url_for("assessment.result", attempt_id=row.id),
        })

    game_rows = (
        GameRun.query
        .filter(
            GameRun.user_id == user_id,
            GameRun.status.in_(["completed", "failed"]),
        )
        .order_by(GameRun.completed_at.desc())
        .limit(8)
        .all()
    )
    for row in game_rows:
        if not row.completed_at:
            continue
        events.append({
            "at": row.completed_at,
            "kind": "game",
            "icon": "bi-controller",
            "title": f"Word Runner · Tier {row.difficulty_tier}",
            "detail": f"{row.status.title()} · {row.correct_answers}/{row.questions_answered} challenge answers correct",
            "url": url_for("game.index"),
        })

    for row in SpeakingAttempt.query.filter_by(user_id=user_id).order_by(SpeakingAttempt.created_at.desc()).limit(4).all():
        events.append({
            "at": row.created_at, "kind": "speaking", "icon": "bi-mic-fill",
            "title": f"Speaking · {row.exercise.title}",
            "detail": f"{row.word_count} recognized words" + (f" · {row.similarity_score}% transcript similarity" if row.similarity_score is not None else ""),
            "url": url_for("speaking.practice", exercise_id=row.exercise_id),
        })
    for row in WritingSubmission.query.filter_by(user_id=user_id).order_by(WritingSubmission.created_at.desc()).limit(4).all():
        events.append({
            "at": row.created_at, "kind": "writing", "icon": "bi-pencil-square",
            "title": f"Writing · {row.prompt.title}",
            "detail": f"Draft {row.revision_number} · {row.word_count} words",
            "url": url_for("writing.result", submission_id=row.id),
        })
    for row in ArcadeRun.query.filter_by(user_id=user_id, status="completed").order_by(ArcadeRun.completed_at.desc()).limit(4).all():
        events.append({
            "at": row.completed_at or row.started_at, "kind": "arcade", "icon": "bi-joystick",
            "title": f"Arcade · {row.game_type.replace('_', ' ').title()}",
            "detail": f"{row.score} points · {row.rounds_correct}/{row.rounds_total} successful rounds",
            "url": url_for("arcade.index"),
        })

    events.sort(key=lambda event: event["at"], reverse=True)
    return events[:10]


def _next_action(user_id, assessment_stats, path_focus, vocabulary_stats):
    diagnostic = assessment_stats["diagnostic"]
    if diagnostic is None:
        assessment = (
            Assessment.query
            .filter_by(assessment_type="diagnostic", is_published=True)
            .order_by(Assessment.id.asc())
            .first()
        )
        if assessment:
            return {
                "kind": "diagnostic",
                "eyebrow": "START HERE",
                "title": "Take the initial diagnostic",
                "detail": "Create your starting-level estimate and personalized route.",
                "label": "Open diagnostic",
                "url": url_for("assessment.intro", code=assessment.code),
                "icon": "bi-compass-fill",
            }

    if path_focus["required_pending"]:
        row = path_focus["required_pending"][0]
        return {
            "kind": "required",
            "eyebrow": "NEXT REQUIRED TOPIC",
            "title": f"{row.topic.level.code} · {row.topic.title}",
            "detail": row.rationale,
            "label": "Continue required path",
            "url": url_for("main.topic", topic_id=row.topic_id),
            "icon": "bi-bullseye",
        }

    # If a personalized level route is complete, surface its level assessment.
    if diagnostic and diagnostic.estimated_level:
        level = Level.query.filter_by(code=diagnostic.estimated_level).first()
        if level:
            progress = get_level_progress(user_id, level)
            assessment = get_level_assessment(level)
            latest_for_level = next(
                (row for row in assessment_stats["levels"] if row["level"] == level.code),
                None,
            )
            if progress["is_complete"] and assessment and latest_for_level is None:
                return {
                    "kind": "assessment",
                    "eyebrow": "ASSESSMENT READY",
                    "title": f"Take the {level.code} level assessment",
                    "detail": "Your required path for this level is complete.",
                    "label": "Open assessment",
                    "url": url_for("assessment.intro", code=assessment.code),
                    "icon": "bi-clipboard2-check-fill",
                }

    if vocabulary_stats["due"]:
        return {
            "kind": "vocabulary",
            "eyebrow": "SPACED REPETITION",
            "title": f"Review {vocabulary_stats['due']} due vocabulary item{'s' if vocabulary_stats['due'] != 1 else ''}",
            "detail": "Clear due cards before their memory interval stretches further.",
            "label": "Review vocabulary",
            "url": url_for("library.review"),
            "icon": "bi-layers-half",
        }

    if path_focus["recommended_pending"]:
        row = path_focus["recommended_pending"][0]
        return {
            "kind": "recommended",
            "eyebrow": "RECOMMENDED REVIEW",
            "title": f"{row.topic.level.code} · {row.topic.title}",
            "detail": row.rationale,
            "label": "Review topic",
            "url": url_for("main.topic", topic_id=row.topic_id),
            "icon": "bi-stars",
        }

    # Once the personalized starting route is consolidated, return to the
    # normal curriculum above the estimated level.
    estimated_code = assessment_stats.get("estimated_level") or "A1"
    start_index = LEVEL_ORDER.index(estimated_code) if estimated_code in LEVEL_ORDER else 0
    completed_level_codes = {row["level"] for row in assessment_stats["levels"]}
    for code in LEVEL_ORDER[start_index + 1:]:
        level = Level.query.filter_by(code=code).first()
        if not level:
            continue
        progress = get_level_progress(user_id, level)
        if progress["next_topic"]:
            topic = progress["next_topic"]
            return {
                "kind": "progression",
                "eyebrow": "CONTINUE YOUR COURSE",
                "title": f"{code} · {topic.title}",
                "detail": "Continue with the next published lesson above your diagnostic starting level.",
                "label": "Open lesson",
                "url": url_for("main.topic", topic_id=topic.id),
                "icon": "bi-arrow-up-right-circle-fill",
            }
        assessment = get_level_assessment(level)
        if progress["is_complete"] and assessment and code not in completed_level_codes:
            return {
                "kind": "assessment",
                "eyebrow": "ASSESSMENT READY",
                "title": f"Take the {code} level assessment",
                "detail": "All blocking lessons for this level are complete.",
                "label": "Open assessment",
                "url": url_for("assessment.intro", code=assessment.code),
                "icon": "bi-clipboard2-check-fill",
            }

    return {
        "kind": "practice",
        "eyebrow": "KEEP PRACTICING",
        "title": "Reinforce English through Word Runner",
        "detail": "Use your level, learning path and saved vocabulary in a short practice run.",
        "label": "Play Word Runner",
        "url": url_for("game.index"),
        "icon": "bi-controller",
    }


def get_student_insights(user_id):
    if ensure_learning_plan(user_id):
        db.session.flush()

    assessments = _assessment_stats(user_id)
    path = _path_focus(user_id)
    vocabulary = _vocabulary_stats(user_id)
    lessons = _lesson_stats(user_id)
    skills = _formal_skill_profile(user_id)
    game = _game_stats(user_id)
    speaking = _speaking_stats(user_id)
    writing = _writing_stats(user_id)
    arcade = _arcade_stats(user_id)

    return {
        "assessments": assessments,
        "path": path,
        "vocabulary": vocabulary,
        "lessons": lessons,
        "skills": skills,
        "game": game,
        "speaking": speaking,
        "writing": writing,
        "arcade": arcade,
        "next_action": _next_action(user_id, assessments, path, vocabulary),
        "recent_activity": _recent_activity(user_id),
    }


@insights_bp.route("/")
@login_required
def profile():
    insights = get_student_insights(current_user.id)
    # ensure_learning_plan may have created rows and flushed them while building
    # the profile. Commit here so a profile-first visit persists that route.
    db.session.commit()
    return render_template("student_profile.html", insights=insights)
