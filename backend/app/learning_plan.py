from collections import Counter, defaultdict

from . import db
from .models import Assessment, AssessmentAttempt, Topic, TopicProgress, UserTopicPlan


LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
PLAN_STATUSES = ("required", "recommended", "optional", "mastered")
STATUS_LABELS = {
    "required": "Required",
    "recommended": "Recommended",
    "optional": "Optional",
    "mastered": "Strong evidence",
}


def _level_index(code):
    try:
        return LEVEL_ORDER.index(code)
    except ValueError:
        return 0


def latest_completed_diagnostic(user_id):
    return (
        AssessmentAttempt.query
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.status == "completed",
            Assessment.assessment_type == "diagnostic",
        )
        .order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())
        .first()
    )


def _topic_evidence(attempt):
    data = defaultdict(lambda: {"correct": 0, "total": 0})
    linked_ids = {link.question_id for link in attempt.assessment.question_links}

    for answer in attempt.answers:
        if answer.question_id not in linked_ids or answer.selected_option is None:
            continue
        question = answer.question
        if not question or not question.topic_id:
            continue
        item = data[question.topic_id]
        item["total"] += 1
        if answer.is_correct:
            item["correct"] += 1

    for item in data.values():
        item["percentage"] = round((item["correct"] / item["total"]) * 100, 1) if item["total"] else None
    return data


def _classify_topic(topic, estimated_code, evidence):
    estimated_idx = _level_index(estimated_code)
    topic_idx = _level_index(topic.level.code)
    total = int(evidence.get("total", 0) or 0)
    correct = int(evidence.get("correct", 0) or 0)
    percentage = evidence.get("percentage")

    # The personalized route only governs the estimated level and foundations
    # below it. Higher levels retain the normal curriculum requirements.
    if topic_idx > estimated_idx:
        return None

    if topic_idx < estimated_idx:
        if total >= 2:
            if percentage < 60:
                return "required", (
                    f"Foundation gap signal: {correct}/{total} diagnostic items correct. "
                    "This lower-level topic is required before advancing."
                )
            if percentage < 80:
                return "recommended", (
                    f"Foundation review signal: {correct}/{total} diagnostic items correct."
                )
            return "mastered", (
                f"Strong foundation evidence: {correct}/{total} diagnostic items correct."
            )

        if total == 1:
            if correct == 0:
                return "recommended", (
                    "One diagnostic item was missed. This is a review signal, not enough evidence "
                    "to make the lower-level topic mandatory."
                )
            return "optional", (
                "One diagnostic item was answered correctly. The topic remains optional because "
                "one item is not enough to claim mastery."
            )

        return "optional", (
            "This topic is below the estimated starting level and was not directly sampled by the diagnostic."
        )

    # Estimated level: this is the learner's active curriculum. Topics remain
    # required unless the diagnostic provides positive evidence to reduce their priority.
    if total >= 2:
        if percentage < 60:
            return "required", (
                f"Target-level gap signal: {correct}/{total} diagnostic items correct."
            )
        if percentage < 80:
            return "recommended", (
                f"Partial target-level evidence: {correct}/{total} diagnostic items correct."
            )
        return "mastered", (
            f"Strong target-level evidence: {correct}/{total} diagnostic items correct."
        )

    if total == 1:
        if correct == 0:
            return "required", (
                "The sampled target-level item was missed. The topic stays in the required route; "
                "the platform does not treat one item as a full topic diagnosis."
            )
        return "optional", (
            "The sampled target-level item was correct. The topic is optional for now, but this is "
            "not treated as a validated mastery score."
        )

    return "required", (
        "This topic belongs to the estimated starting level but was not directly sampled by the diagnostic, "
        "so it remains part of the core route."
    )


def generate_learning_plan(attempt):
    if not attempt or attempt.status != "completed" or attempt.assessment.assessment_type != "diagnostic":
        return []

    estimated_code = attempt.estimated_level or "A1"
    estimated_idx = _level_index(estimated_code)
    evidence_by_topic = _topic_evidence(attempt)

    UserTopicPlan.query.filter_by(user_id=attempt.user_id).delete(synchronize_session=False)

    topics = (
        Topic.query
        .filter_by(is_published=True)
        .order_by(Topic.level_id.asc(), Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )

    rows = []
    for topic in topics:
        if _level_index(topic.level.code) > estimated_idx:
            continue

        evidence = evidence_by_topic.get(topic.id, {"correct": 0, "total": 0, "percentage": None})
        classified = _classify_topic(topic, estimated_code, evidence)
        if not classified:
            continue
        status, rationale = classified

        row = UserTopicPlan(
            user_id=attempt.user_id,
            topic_id=topic.id,
            diagnostic_attempt_id=attempt.id,
            status=status,
            evidence_correct=int(evidence.get("correct", 0) or 0),
            evidence_total=int(evidence.get("total", 0) or 0),
            evidence_percentage=evidence.get("percentage"),
            rationale=rationale,
        )
        db.session.add(row)
        rows.append(row)

    db.session.flush()
    return rows


def ensure_learning_plan(user_id):
    if UserTopicPlan.query.filter_by(user_id=user_id).first():
        return False
    attempt = latest_completed_diagnostic(user_id)
    if not attempt:
        return False
    generate_learning_plan(attempt)
    return True


def get_learning_plan_summary(user_id):
    rows = (
        UserTopicPlan.query
        .filter_by(user_id=user_id)
        .join(Topic, Topic.id == UserTopicPlan.topic_id)
        .order_by(Topic.level_id.asc(), Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )
    if not rows:
        return None

    attempt = rows[0].diagnostic_attempt
    counts = Counter(row.status for row in rows)
    by_level = defaultdict(list)
    for row in rows:
        by_level[row.topic.level.code].append(row)

    required_ids = [row.topic_id for row in rows if row.status == "required"]
    required_completed = (
        TopicProgress.query
        .filter(
            TopicProgress.user_id == user_id,
            TopicProgress.topic_id.in_(required_ids),
            TopicProgress.completed.is_(True),
        )
        .count()
        if required_ids
        else 0
    )

    return {
        "rows": rows,
        "by_level": dict(by_level),
        "counts": {status: counts.get(status, 0) for status in PLAN_STATUSES},
        "estimated_level": attempt.estimated_level if attempt else None,
        "diagnostic_attempt": attempt,
        "total": len(rows),
        "required_completed": required_completed,
        "required_total": len(required_ids),
        "required_remaining": max(0, len(required_ids) - required_completed),
    }


def get_plan_rows_for_level(user_id, level_id):
    return (
        UserTopicPlan.query
        .join(Topic, Topic.id == UserTopicPlan.topic_id)
        .filter(
            UserTopicPlan.user_id == user_id,
            Topic.level_id == level_id,
        )
        .order_by(Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )
