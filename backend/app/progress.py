from datetime import datetime

from . import db
from .models import Topic, TopicProgress, Assessment, UserTopicPlan


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

    if progress.best_total == 0 or percentage > progress.best_percentage:
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
    progress_by_topic = {row.topic_id: row for row in progress_rows}

    overall_completed = sum(
        1 for topic in topics
        if progress_by_topic.get(topic.id) and progress_by_topic[topic.id].completed
    )
    overall_total = len(topics)
    overall_percentage = round((overall_completed / overall_total) * 100, 1) if overall_total else 0.0

    plan_rows = (
        UserTopicPlan.query
        .filter(
            UserTopicPlan.user_id == user_id,
            UserTopicPlan.topic_id.in_(topic_ids),
        )
        .all()
        if topic_ids
        else []
    )
    plan_by_topic = {row.topic_id: row for row in plan_rows}
    personalized = bool(plan_rows)

    if personalized:
        required_topics = [topic for topic in topics if plan_by_topic.get(topic.id) and plan_by_topic[topic.id].status == "required"]
        required_completed = sum(
            1 for topic in required_topics
            if progress_by_topic.get(topic.id) and progress_by_topic[topic.id].completed
        )
        required_total = len(required_topics)
        percentage = 100.0 if required_total == 0 else round((required_completed / required_total) * 100, 1)
        is_complete = required_completed == required_total
        next_topic = next(
            (
                topic for topic in required_topics
                if not (progress_by_topic.get(topic.id) and progress_by_topic[topic.id].completed)
            ),
            None,
        )
        recommended_next_topic = next(
            (
                topic for topic in topics
                if plan_by_topic.get(topic.id)
                and plan_by_topic[topic.id].status == "recommended"
                and not (progress_by_topic.get(topic.id) and progress_by_topic[topic.id].completed)
            ),
            None,
        )
        completed = required_completed
        total = required_total
    else:
        completed = overall_completed
        total = overall_total
        percentage = overall_percentage
        next_topic = next(
            (
                topic for topic in topics
                if not (progress_by_topic.get(topic.id) and progress_by_topic[topic.id].completed)
            ),
            None,
        )
        recommended_next_topic = None
        is_complete = bool(total) and completed == total

    return {
        "topics": topics,
        "progress_by_topic": progress_by_topic,
        "plan_by_topic": plan_by_topic,
        "personalized": personalized,
        "completed": completed,
        "total": total,
        "percentage": percentage,
        "next_topic": next_topic,
        "recommended_next_topic": recommended_next_topic,
        "is_complete": is_complete,
        "overall_completed": overall_completed,
        "overall_total": overall_total,
        "overall_percentage": overall_percentage,
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

    if progress["personalized"]:
        remaining = max(0, progress["total"] - progress["completed"])
        reason = (
            None
            if progress["is_complete"]
            else (
                f"Complete the {remaining} remaining required lesson"
                f"{'s' if remaining != 1 else ''} in your personalized {assessment.level.code} path."
            )
        )
    else:
        reason = (
            None
            if progress["is_complete"]
            else (
                f"Complete all {progress['total']} published lessons "
                f"to unlock this assessment."
            )
        )

    return {
        "unlocked": progress["is_complete"],
        "reason": reason,
        "progress": progress,
    }
