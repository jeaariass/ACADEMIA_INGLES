from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import joinedload

from . import db
from .models import (
    Answer,
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    Attempt,
    GameChallenge,
    GameRun,
    Level,
    LibraryItem,
    Question,
    SavedVocabulary,
    Topic,
    TopicProgress,
    User,
    UserTopicPlan,
)

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
SKILL_ORDER = ["grammar", "vocabulary", "reading", "listening", "integrated"]
MIN_ITEM_EVIDENCE = 10


def _safe_pct(correct: int, total: int):
    return round((correct / total) * 100, 1) if total else None


def _aggregate_response_rows(model, *, question_column, correct_column, selected_column=None):
    filters = []
    if selected_column is not None:
        filters.append(selected_column.isnot(None))

    query = (
        db.session.query(
            question_column.label("question_id"),
            func.count().label("responses"),
            func.sum(case((correct_column.is_(True), 1), else_=0)).label("correct"),
        )
        .filter(*filters)
        .group_by(question_column)
    )

    return {
        row.question_id: {
            "responses": int(row.responses or 0),
            "correct": int(row.correct or 0),
        }
        for row in query.all()
        if row.question_id is not None
    }


def _assessment_time_rows():
    rows = (
        db.session.query(
            AssessmentAnswer.question_id.label("question_id"),
            func.avg(AssessmentAnswer.response_time_seconds).label("avg_seconds"),
        )
        .filter(
            AssessmentAnswer.selected_option.isnot(None),
            AssessmentAnswer.response_time_seconds.isnot(None),
        )
        .group_by(AssessmentAnswer.question_id)
        .all()
    )
    return {
        row.question_id: round(float(row.avg_seconds), 1)
        for row in rows
        if row.question_id is not None and row.avg_seconds is not None
    }


def _item_status(level_difficulty: int, academic_total: int, academic_rate):
    if academic_total < MIN_ITEM_EVIDENCE:
        return "insufficient"
    if academic_rate is None:
        return "insufficient"

    if level_difficulty >= 4 and academic_rate >= 80:
        return "difficulty_mismatch"
    if level_difficulty <= 2 and academic_rate <= 55:
        return "difficulty_mismatch"
    if academic_rate >= 90:
        return "too_easy"
    if academic_rate <= 40:
        return "too_hard"
    return "healthy"


def build_question_analysis(
    *,
    level_code: str | None = None,
    skill: str | None = None,
    status: str | None = None,
    min_responses: int = 0,
):
    practice = _aggregate_response_rows(
        Answer,
        question_column=Answer.question_id,
        correct_column=Answer.is_correct,
    )
    formal = _aggregate_response_rows(
        AssessmentAnswer,
        question_column=AssessmentAnswer.question_id,
        correct_column=AssessmentAnswer.is_correct,
        selected_column=AssessmentAnswer.selected_option,
    )
    game = _aggregate_response_rows(
        GameChallenge,
        question_column=GameChallenge.question_id,
        correct_column=GameChallenge.is_correct,
        selected_column=GameChallenge.selected_option,
    )
    average_times = _assessment_time_rows()

    questions = (
        Question.query
        .options(joinedload(Question.topic).joinedload(Topic.level))
        .order_by(Question.id.asc())
        .all()
    )

    rows = []
    status_counts = defaultdict(int)
    for question in questions:
        topic = question.topic
        level = topic.level if topic else None
        level_value = level.code if level else "—"
        level_difficulty = max(1, min(5, int(question.level_difficulty or 3)))

        p = practice.get(question.id, {"responses": 0, "correct": 0})
        f = formal.get(question.id, {"responses": 0, "correct": 0})
        g = game.get(question.id, {"responses": 0, "correct": 0})

        academic_total = p["responses"] + f["responses"]
        academic_correct = p["correct"] + f["correct"]
        academic_rate = _safe_pct(academic_correct, academic_total)
        game_rate = _safe_pct(g["correct"], g["responses"])
        item_status = _item_status(level_difficulty, academic_total, academic_rate)
        status_counts[item_status] += 1

        row = {
            "id": question.id,
            "code": question.code or f"Q{question.id}",
            "level": level_value,
            "topic": topic.title if topic else "—",
            "topic_code": topic.code if topic else None,
            "skill": question.skill,
            "question_type": question.question_type,
            "level_difficulty": level_difficulty,
            "prompt": question.prompt,
            "is_active": bool(question.is_active),
            "practice_responses": p["responses"],
            "formal_responses": f["responses"],
            "academic_responses": academic_total,
            "academic_correct": academic_correct,
            "academic_rate": academic_rate,
            "avg_response_seconds": average_times.get(question.id),
            "game_responses": g["responses"],
            "game_correct": g["correct"],
            "game_rate": game_rate,
            "status": item_status,
        }

        if level_code and level_code != "ALL" and level_value != level_code:
            continue
        if skill and skill != "ALL" and question.skill != skill:
            continue
        if status and status != "ALL" and item_status != status:
            continue
        if academic_total < max(0, int(min_responses or 0)):
            continue
        rows.append(row)

    priority = {
        "difficulty_mismatch": 0,
        "too_hard": 1,
        "too_easy": 2,
        "insufficient": 3,
        "healthy": 4,
    }
    rows.sort(
        key=lambda row: (
            priority.get(row["status"], 9),
            -row["academic_responses"],
            row["level"] if row["level"] in LEVEL_ORDER else "ZZ",
            row["code"],
        )
    )

    return rows, dict(status_counts)


def _difficulty_distribution():
    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    result = []
    for level in levels:
        counts = {difficulty: 0 for difficulty in range(1, 6)}
        questions = (
            Question.query
            .join(Topic, Question.topic_id == Topic.id)
            .filter(Topic.level_id == level.id)
            .all()
        )
        for question in questions:
            difficulty = max(1, min(5, int(question.level_difficulty or 3)))
            counts[difficulty] += 1
        populated = sum(1 for count in counts.values() if count)
        result.append({
            "code": level.code,
            "counts": counts,
            "total": len(questions),
            "populated": populated,
            "adaptive_ready": populated >= 3,
        })
    return result


def _topic_performance(question_rows):
    aggregate = {}
    for row in question_rows:
        if not row["topic_code"]:
            continue
        key = row["topic_code"]
        entry = aggregate.setdefault(key, {
            "topic_code": row["topic_code"],
            "topic": row["topic"],
            "level": row["level"],
            "responses": 0,
            "correct": 0,
            "questions_with_evidence": 0,
        })
        entry["responses"] += row["academic_responses"]
        entry["correct"] += row["academic_correct"]
        if row["academic_responses"]:
            entry["questions_with_evidence"] += 1

    rows = []
    for entry in aggregate.values():
        entry["rate"] = _safe_pct(entry["correct"], entry["responses"])
        rows.append(entry)

    rows.sort(
        key=lambda entry: (
            entry["rate"] if entry["rate"] is not None else 101,
            -entry["responses"],
        )
    )
    return rows


def _student_engagement_summary():
    students = User.query.filter_by(role="student").all()
    student_ids = {student.id for student in students}
    total_students = len(students)

    diagnostic_assessment_ids = {
        row.id
        for row in Assessment.query.filter_by(assessment_type="diagnostic").all()
    }
    diagnosed_ids = set()
    if diagnostic_assessment_ids:
        diagnosed_ids = {
            row.user_id
            for row in AssessmentAttempt.query.filter(
                AssessmentAttempt.assessment_id.in_(diagnostic_assessment_ids),
                AssessmentAttempt.status == "completed",
            ).all()
            if row.user_id in student_ids
        }

    plan_ids = {
        row.user_id
        for row in UserTopicPlan.query.with_entities(UserTopicPlan.user_id).distinct().all()
        if row.user_id in student_ids
    }
    vocab_ids = {
        row.user_id
        for row in SavedVocabulary.query.with_entities(SavedVocabulary.user_id).distinct().all()
        if row.user_id in student_ids
    }
    game_ids = {
        row.user_id
        for row in GameRun.query.with_entities(GameRun.user_id).distinct().all()
        if row.user_id in student_ids
    }

    cutoff = datetime.utcnow() - timedelta(days=30)
    active_ids = set()
    active_ids.update(
        row.user_id
        for row in Attempt.query.filter(Attempt.created_at >= cutoff).all()
        if row.user_id in student_ids
    )
    active_ids.update(
        row.user_id
        for row in AssessmentAttempt.query.filter(AssessmentAttempt.started_at >= cutoff).all()
        if row.user_id in student_ids
    )
    active_ids.update(
        row.user_id
        for row in GameRun.query.filter(GameRun.started_at >= cutoff).all()
        if row.user_id in student_ids
    )
    active_ids.update(
        row.user_id
        for row in SavedVocabulary.query.filter(SavedVocabulary.updated_at >= cutoff).all()
        if row.user_id in student_ids
    )

    return {
        "students": total_students,
        "diagnosed": len(diagnosed_ids),
        "diagnosed_pct": _safe_pct(len(diagnosed_ids), total_students),
        "personalized": len(plan_ids),
        "personalized_pct": _safe_pct(len(plan_ids), total_students),
        "vocabulary_users": len(vocab_ids),
        "vocabulary_pct": _safe_pct(len(vocab_ids), total_students),
        "game_users": len(game_ids),
        "game_pct": _safe_pct(len(game_ids), total_students),
        "active_30d": len(active_ids),
        "active_30d_pct": _safe_pct(len(active_ids), total_students),
    }


def _platform_totals():
    completed_games = GameRun.query.filter_by(status="completed").count()
    game_runs = GameRun.query.count()
    game_answered = db.session.query(func.sum(GameRun.questions_answered)).scalar() or 0
    game_correct = db.session.query(func.sum(GameRun.correct_answers)).scalar() or 0

    correct_reviews = db.session.query(func.sum(SavedVocabulary.correct_reviews)).scalar() or 0
    incorrect_reviews = db.session.query(func.sum(SavedVocabulary.incorrect_reviews)).scalar() or 0
    review_total = int(correct_reviews + incorrect_reviews)

    return {
        "practice_attempts": Attempt.query.count(),
        "formal_attempts": AssessmentAttempt.query.filter_by(status="completed").count(),
        "lesson_completions": TopicProgress.query.filter_by(completed=True).count(),
        "saved_vocabulary": SavedVocabulary.query.count(),
        "vocabulary_reviews": review_total,
        "vocabulary_review_accuracy": _safe_pct(int(correct_reviews), review_total),
        "library_items": LibraryItem.query.filter_by(is_published=True).count(),
        "game_runs": game_runs,
        "game_completed": completed_games,
        "game_completion_rate": _safe_pct(completed_games, game_runs),
        "game_challenge_accuracy": _safe_pct(int(game_correct), int(game_answered)),
    }


def _library_source_usage():
    rows = (
        db.session.query(
            LibraryItem.code,
            LibraryItem.title,
            LibraryItem.level_code,
            func.count(SavedVocabulary.id).label("saved_count"),
            func.count(func.distinct(SavedVocabulary.user_id)).label("users"),
        )
        .join(SavedVocabulary, SavedVocabulary.library_item_id == LibraryItem.id)
        .group_by(LibraryItem.id, LibraryItem.code, LibraryItem.title, LibraryItem.level_code)
        .order_by(func.count(SavedVocabulary.id).desc())
        .limit(10)
        .all()
    )
    return [
        {
            "code": row.code,
            "title": row.title,
            "level": row.level_code,
            "saved_count": int(row.saved_count or 0),
            "users": int(row.users or 0),
        }
        for row in rows
    ]


def build_admin_analytics():
    all_question_rows, status_counts = build_question_analysis()
    evidenced = [row for row in all_question_rows if row["academic_responses"] >= MIN_ITEM_EVIDENCE]
    evidenced_count = len(evidenced)
    flagged = [
        row for row in evidenced
        if row["status"] in {"too_easy", "too_hard", "difficulty_mismatch"}
    ]

    topic_rows = _topic_performance(all_question_rows)
    topic_with_evidence = [row for row in topic_rows if row["responses"] >= MIN_ITEM_EVIDENCE]

    return {
        "generated_at": datetime.utcnow(),
        "engagement": _student_engagement_summary(),
        "totals": _platform_totals(),
        "question_health": {
            "total_questions": len(all_question_rows),
            "with_evidence": evidenced_count,
            "flagged": len(flagged),
            "flagged_pct": _safe_pct(len(flagged), evidenced_count),
            "status_counts": status_counts,
            "min_evidence": MIN_ITEM_EVIDENCE,
            "top_flagged": flagged[:12],
        },
        "difficulty_distribution": _difficulty_distribution(),
        "topics_to_review": topic_with_evidence[:10],
        "library_sources": _library_source_usage(),
    }
