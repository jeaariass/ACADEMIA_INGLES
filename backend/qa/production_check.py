#!/usr/bin/env python3
"""Production-oriented integrity checks for English Practice Hub.

Run inside the backend container:
    python qa/production_check.py

Exit code 1 means a release-blocking problem was found. Warnings are printed but
do not fail the command.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import func, or_, text

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app, db
from app.models import Assessment, GameVocabulary, GameVocabularyCategory, LibraryItem, Question, Topic, User

EXPECTED_ALEMBIC_HEAD = "f0d24b6a8e85"


class Reporter:
    def __init__(self):
        self.failures = []
        self.warnings = []

    def ok(self, message):
        print(f"[PASS] {message}")

    def warn(self, message):
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def fail(self, message):
        self.failures.append(message)
        print(f"[FAIL] {message}")


def main():
    report = Reporter()
    app = create_app()

    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            report.ok("Database connection")
        except Exception as exc:
            report.fail(f"Database connection failed: {exc}")
            return 1

        try:
            revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision == EXPECTED_ALEMBIC_HEAD:
                report.ok(f"Alembic revision {revision}")
            else:
                report.fail(
                    f"Database revision is {revision!r}; expected {EXPECTED_ALEMBIC_HEAD}. Run 'flask db upgrade'."
                )
        except Exception as exc:
            report.fail(f"Could not read alembic_version: {exc}")

        admins = User.query.filter_by(role="admin").count()
        if admins:
            report.ok(f"Administrator accounts: {admins}")
        else:
            report.fail("No administrator account exists")

        invalid_difficulty = Question.query.filter(
            or_(
                Question.level_difficulty.is_(None),
                Question.level_difficulty < 1,
                Question.level_difficulty > 5,
            )
        ).count()
        if invalid_difficulty:
            report.fail(f"Questions with invalid level_difficulty: {invalid_difficulty}")
        else:
            report.ok("Question level_difficulty values are within 1-5")

        invalid_correct = Question.query.filter(~Question.correct_option.in_(["A", "B", "C", "D"])).count()
        if invalid_correct:
            report.fail(f"Questions with invalid correct_option: {invalid_correct}")
        else:
            report.ok("Question correct options are valid")

        empty_active = Question.query.filter(
            Question.is_active.is_(True),
            or_(Question.prompt == "", Question.prompt.is_(None)),
        ).count()
        if empty_active:
            report.fail(f"Active questions with empty prompt: {empty_active}")
        else:
            report.ok("Active questions contain prompts")

        uncoded_topics = Topic.query.filter(Topic.is_published.is_(True), Topic.code.is_(None)).count()
        if uncoded_topics:
            report.warn(
                f"Published topics without stable code: {uncoded_topics}. Assign codes before relying on bulk updates."
            )

        empty_readings = LibraryItem.query.filter(
            LibraryItem.is_published.is_(True),
            or_(LibraryItem.content_text == "", LibraryItem.content_text.is_(None)),
        ).count()
        if empty_readings:
            report.fail(f"Published library readings with empty content: {empty_readings}")
        else:
            report.ok("Published library readings contain content")

        invalid_game_vocab = GameVocabulary.query.filter(
            or_(
                GameVocabulary.english == "",
                GameVocabulary.spanish == "",
                GameVocabulary.kids_difficulty < 1,
                GameVocabulary.kids_difficulty > 3,
                GameVocabulary.standard_difficulty < 1,
                GameVocabulary.standard_difficulty > 5,
            )
        ).count()
        if invalid_game_vocab:
            report.fail(f"Invalid shared game vocabulary rows: {invalid_game_vocab}")
        else:
            report.ok("Shared game vocabulary is structurally valid")

        orphan_game_vocab = GameVocabulary.query.outerjoin(
            GameVocabularyCategory, GameVocabularyCategory.id == GameVocabulary.category_id
        ).filter(GameVocabularyCategory.id.is_(None)).count()
        if orphan_game_vocab:
            report.fail(f"Game vocabulary rows without category: {orphan_game_vocab}")
        else:
            report.ok("Game vocabulary categories are linked")

        empty_assessments = [
            item.code
            for item in Assessment.query.filter_by(is_published=True).all()
            if not item.question_links
        ]
        if empty_assessments:
            report.fail("Published assessments without questions: " + ", ".join(empty_assessments))
        else:
            report.ok("Published assessments contain linked questions")

        if (os.getenv("APP_ENV") or "development").lower() == "production":
            if os.getenv("SEED_DEMO_USERS", "false").lower() in {"1", "true", "yes", "on"}:
                report.warn("SEED_DEMO_USERS is enabled in production")
            if not os.getenv("ALLOWED_HOSTS"):
                report.warn("ALLOWED_HOSTS is empty; configure it for the public deployment")
            if os.getenv("SESSION_COOKIE_SECURE", "false").lower() not in {"1", "true", "yes", "on"}:
                report.fail("SESSION_COOKIE_SECURE must be enabled in production")

    print()
    print(f"Summary: {len(report.failures)} failure(s), {len(report.warnings)} warning(s).")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
