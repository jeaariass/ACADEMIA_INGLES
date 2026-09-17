import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app, db
from app.models import Attempt, TopicProgress


def sync_progress():
    attempts = (
        Attempt.query
        .order_by(Attempt.user_id, Attempt.topic_id, Attempt.created_at.asc())
        .all()
    )

    grouped = defaultdict(list)

    for attempt in attempts:
        grouped[(attempt.user_id, attempt.topic_id)].append(attempt)

    created = 0
    updated = 0

    for (user_id, topic_id), topic_attempts in grouped.items():
        progress = TopicProgress.query.filter_by(
            user_id=user_id,
            topic_id=topic_id,
        ).first()

        if not progress:
            progress = TopicProgress(
                user_id=user_id,
                topic_id=topic_id,
            )
            db.session.add(progress)
            created += 1
        else:
            updated += 1

        first_attempt = topic_attempts[0]
        last_attempt = topic_attempts[-1]

        best_attempt = max(
            topic_attempts,
            key=lambda a: (
                (a.score / a.total)
                if a.total
                else 0
            ),
        )

        best_percentage = (
            round(
                (best_attempt.score / best_attempt.total) * 100,
                1,
            )
            if best_attempt.total
            else 0.0
        )

        progress.completed = True
        progress.completed_at = (
            progress.completed_at
            or first_attempt.created_at
        )
        progress.last_practiced_at = last_attempt.created_at
        progress.last_attempt_id = last_attempt.id
        progress.best_score = best_attempt.score
        progress.best_total = best_attempt.total
        progress.best_percentage = best_percentage

    db.session.commit()

    print(
        f"[progress-sync] Created {created} progress row(s), "
        f"updated {updated} row(s)."
    )
    print(
        f"[progress-sync] Processed {len(attempts)} practice attempt(s)."
    )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        sync_progress()
