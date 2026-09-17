from datetime import datetime

from . import db
from .models import Topic, TopicProgress, Assessment


def update_topic_progress(user_id, topic, attempt):
    progress = TopicProgress.query.filter_by(
        user_id=user_id,
        topic_id=topic.id,
    ).first()

    if not progress:
        progress = TopicProgress(
            user_id=user_id,
            topic_id=topic.id,
        )
        db.session.add(progress)

    percentage = (
        round((attempt.score / attempt.total) * 100, 1)
        if attempt.total
        else 0.0
    )

    progress.completed = True
    if progress.completed_at is None:
        progress.completed_at = datetime.utcnow()

    progress.last_practiced_at = attempt.created_at or datetime.utcnow()
    progress.last_attempt_id = attempt.id

    if (
        progress.best_total == 0
        or percentage > progress.best_percentage
    ):
        progress.best_score = attempt.score
        progress.best_total = attempt.total
        progress.best_percentage = percentage

    return progress


def get_level_progress(user_id, level):
    topics = (
        Topic.query
        .filter_by(level_id=level.id, is_published=True)
        .order_by(Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )

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

    progress_by_topic = {
        row.topic_id: row
        for row in progress_rows
    }

    completed = sum(
        1
        for topic in topics
        if progress_by_topic.get(topic.id)
        and progress_by_topic[topic.id].completed
    )

    total = len(topics)
    percentage = round((completed / total) * 100, 1) if total else 0.0

    next_topic = next(
        (
            topic
            for topic in topics
            if not (
                progress_by_topic.get(topic.id)
                and progress_by_topic[topic.id].completed
            )
        ),
        None,
    )

    return {
        "topics": topics,
        "progress_by_topic": progress_by_topic,
        "completed": completed,
        "total": total,
        "percentage": percentage,
        "next_topic": next_topic,
        "is_complete": bool(total) and completed == total,
    }



def get_course_progress(user_id):
    topics = (
        Topic.query
        .filter_by(is_published=True)
        .order_by(Topic.level_id.asc(), Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )
    topic_ids = [topic.id for topic in topics]

    completed = (
        TopicProgress.query
        .filter(
            TopicProgress.user_id == user_id,
            TopicProgress.topic_id.in_(topic_ids),
            TopicProgress.completed.is_(True),
        )
        .count()
        if topic_ids
        else 0
    )

    total = len(topics)
    percentage = round((completed / total) * 100, 1) if total else 0.0

    return {
        "completed": completed,
        "total": total,
        "percentage": percentage,
        "is_complete": bool(total) and completed == total,
    }


def get_level_assessment(level):
    return (
        Assessment.query
        .filter_by(
            level_id=level.id,
            assessment_type="level",
            is_published=True,
        )
        .order_by(Assessment.id.asc())
        .first()
    )


def assessment_access(user, assessment):
    if user.is_admin:
        return {
            "unlocked": True,
            "reason": "Administrator access",
            "progress": None,
        }

    if assessment.assessment_type == "final":
        progress = get_course_progress(user.id)
        return {
            "unlocked": progress["is_complete"],
            "reason": (
                None
                if progress["is_complete"]
                else (
                    f"Complete all {progress['total']} published lessons across "
                    f"A1–C2 to unlock the final comprehensive assessment."
                )
            ),
            "progress": progress,
        }

    if assessment.assessment_type != "level" or not assessment.level:
        return {
            "unlocked": True,
            "reason": None,
            "progress": None,
        }

    progress = get_level_progress(user.id, assessment.level)

    return {
        "unlocked": progress["is_complete"],
        "reason": (
            None
            if progress["is_complete"]
            else (
                f"Complete all {progress['total']} published lessons "
                f"to unlock this assessment."
            )
        ),
        "progress": progress,
    }
