#!/usr/bin/env python3
"""
Database integrity audit for English Practice Hub.

Run:
    python scripts/audit_database.py

Optional:
    python scripts/audit_database.py --json-out /tmp/db_qa.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Allow direct execution as /app/scripts/audit_database.py.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app, db
from app.models import (
    Level,
    Topic,
    Question,
    Passage,
    Assessment,
    AssessmentQuestion,
    AssessmentAttempt,
    AssessmentAnswer,
    Attempt,
    Answer,
    TopicProgress,
)


def issue(severity, code, message, **details):
    return {"severity": severity, "code": code, "message": message, "details": details}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    app = create_app()
    problems = []
    stats = {}

    with app.app_context():
        levels = Level.query.order_by(Level.id).all()
        topics = Topic.query.all()
        questions = Question.query.all()
        passages = Passage.query.all()
        assessments = Assessment.query.all()
        links = AssessmentQuestion.query.all()
        assessment_attempts = AssessmentAttempt.query.all()
        assessment_answers = AssessmentAnswer.query.all()
        practice_attempts = Attempt.query.all()
        practice_answers = Answer.query.all()
        progress_rows = TopicProgress.query.all()

        stats.update({
            "levels": len(levels),
            "topics": len(topics),
            "questions": len(questions),
            "passages": len(passages),
            "assessments": len(assessments),
            "assessment_links": len(links),
            "assessment_attempts": len(assessment_attempts),
            "assessment_answers": len(assessment_answers),
            "practice_attempts": len(practice_attempts),
            "practice_answers": len(practice_answers),
            "topic_progress_rows": len(progress_rows),
        })

        # Expected academic skeleton.
        level_codes = [level.code for level in levels]
        for expected in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            if expected not in level_codes:
                problems.append(issue("ERROR", "LEVEL_MISSING", f"Level {expected} does not exist in the database."))

        # Topic counts.
        topic_counts = Counter(topic.level.code for topic in topics if topic.level)
        stats["topics_by_level"] = dict(sorted(topic_counts.items()))
        for code in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            count = topic_counts.get(code, 0)
            if count != 15:
                problems.append(issue("ERROR", "TOPIC_COUNT", f"{code} has {count} topics; expected 15.", level=code, found=count))

        # Duplicate content codes when fields exist.
        def check_duplicate_attr(rows, attr, label):
            values = defaultdict(list)
            for row in rows:
                value = getattr(row, attr, None)
                if value:
                    values[value].append(row.id)
            for value, ids in values.items():
                if len(ids) > 1:
                    problems.append(issue("ERROR", f"{label}_CODE_DUPLICATE", f"{label} code {value!r} occurs multiple times.", ids=ids))

        check_duplicate_attr(topics, "code", "TOPIC")
        check_duplicate_attr(questions, "code", "QUESTION")
        check_duplicate_attr(passages, "code", "PASSAGE")
        check_duplicate_attr(assessments, "code", "ASSESSMENT")

        # Question integrity.
        for q in questions:
            opts = [
                (q.option_a or "").strip(),
                (q.option_b or "").strip(),
                (q.option_c or "").strip(),
                (q.option_d or "").strip(),
            ]
            if any(not x for x in opts):
                problems.append(issue("ERROR", "QUESTION_EMPTY_OPTION", f"Question {q.id} has an empty option.", question_id=q.id))
            if len(set(x.lower() for x in opts)) != 4:
                problems.append(issue("ERROR", "QUESTION_DUPLICATE_OPTION", f"Question {q.id} has duplicated options.", question_id=q.id))
            if (q.correct_option or "").upper() not in {"A", "B", "C", "D"}:
                problems.append(issue("ERROR", "QUESTION_BAD_KEY", f"Question {q.id} has invalid correct_option.", question_id=q.id, correct_option=q.correct_option))
            if not q.topic_id:
                problems.append(issue("ERROR", "QUESTION_NO_TOPIC", f"Question {q.id} is not linked to a topic.", question_id=q.id))

        # Passage integrity.
        for p in passages:
            if p.passage_type == "reading" and not (p.content_text or "").strip():
                problems.append(issue("ERROR", "READING_EMPTY", f"Reading passage {p.id} has no text.", passage_id=p.id))
            if p.passage_type == "listening" and not (p.audio_text or "").strip():
                problems.append(issue("ERROR", "LISTENING_EMPTY", f"Listening passage {p.id} has no audio_text.", passage_id=p.id))

        # Per-topic practice architecture.
        for topic in topics:
            direct = Question.query.filter_by(topic_id=topic.id, passage_id=None).count()
            passage_count = Passage.query.filter_by(topic_id=topic.id).count()
            passage_questions = (
                Question.query
                .join(Passage, Question.passage_id == Passage.id)
                .filter(Passage.topic_id == topic.id)
                .count()
            )
            total = direct + passage_questions
            if direct != 10 or passage_count != 2 or passage_questions != 5 or total != 15:
                problems.append(issue(
                    "ERROR",
                    "TOPIC_ARCHITECTURE",
                    f"{topic.level.code if topic.level else '?'} · {topic.title}: direct={direct}, passages={passage_count}, passage_questions={passage_questions}, total={total}",
                    topic_id=topic.id,
                ))

        # Assessment counts.
        expected_assessments = {
            "A1_LEVEL_ASSESSMENT": 40,
            "A2_LEVEL_ASSESSMENT": 40,
            "B1_LEVEL_ASSESSMENT": 40,
            "B2_LEVEL_ASSESSMENT": 40,
            "C1_LEVEL_ASSESSMENT": 40,
            "C2_LEVEL_ASSESSMENT": 40,
            "INITIAL_DIAGNOSTIC_A1_C2": 108,
            "FINAL_COMPREHENSIVE_A1_C2": 72,
        }
        assessment_counts = {}
        for assessment in assessments:
            count = AssessmentQuestion.query.filter_by(assessment_id=assessment.id).count()
            assessment_counts[assessment.code] = count
        stats["assessment_question_counts"] = assessment_counts

        for code, expected in expected_assessments.items():
            assessment = next((x for x in assessments if x.code == code), None)
            if not assessment:
                problems.append(issue("ERROR", "ASSESSMENT_MISSING", f"Required assessment {code} is missing."))
                continue
            count = assessment_counts.get(code, 0)
            if count != expected:
                problems.append(issue("ERROR", "ASSESSMENT_COUNT", f"{code} has {count} linked questions; expected {expected}.", code=code, found=count))

        # Assessment link integrity.
        seen_link_pairs = Counter((link.assessment_id, link.question_id) for link in links)
        for pair, count in seen_link_pairs.items():
            if count > 1:
                problems.append(issue("ERROR", "ASSESSMENT_LINK_DUPLICATE", "Same question linked multiple times to one assessment.", assessment_id=pair[0], question_id=pair[1], count=count))

        # Attempt / answer consistency.
        for attempt in assessment_attempts:
            answers = AssessmentAnswer.query.filter_by(assessment_attempt_id=attempt.id).all()
            answered = [a for a in answers if a.selected_option is not None]
            correct = sum(1 for a in answered if a.is_correct)
            if attempt.status == "completed":
                if attempt.total != len(answered):
                    problems.append(issue("WARNING", "ASSESSMENT_ATTEMPT_TOTAL", f"Attempt {attempt.id}: stored total={attempt.total}, answered={len(answered)}.", attempt_id=attempt.id))
                if attempt.score != correct:
                    problems.append(issue("WARNING", "ASSESSMENT_ATTEMPT_SCORE", f"Attempt {attempt.id}: stored score={attempt.score}, calculated={correct}.", attempt_id=attempt.id))

        for attempt in practice_attempts:
            answers = Answer.query.filter_by(attempt_id=attempt.id).all()
            correct = sum(1 for a in answers if a.is_correct)
            if attempt.total != len(answers):
                problems.append(issue("WARNING", "PRACTICE_ATTEMPT_TOTAL", f"Practice attempt {attempt.id}: stored total={attempt.total}, answers={len(answers)}.", attempt_id=attempt.id))
            if attempt.score != correct:
                problems.append(issue("WARNING", "PRACTICE_ATTEMPT_SCORE", f"Practice attempt {attempt.id}: stored score={attempt.score}, calculated={correct}.", attempt_id=attempt.id))

        # TopicProgress sanity.
        duplicate_progress = Counter((p.user_id, p.topic_id) for p in progress_rows)
        for pair, count in duplicate_progress.items():
            if count > 1:
                problems.append(issue("ERROR", "PROGRESS_DUPLICATE", "Duplicate TopicProgress rows.", user_id=pair[0], topic_id=pair[1], count=count))

    errors = sum(1 for p in problems if p["severity"] == "ERROR")
    warnings = sum(1 for p in problems if p["severity"] == "WARNING")

    print("[db-qa] English Practice Hub database audit")
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"[db-qa] {key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            print(f"[db-qa] {key}: {value}")
    print(f"[db-qa] Errors: {errors}")
    print(f"[db-qa] Warnings: {warnings}")

    for p in problems:
        print(f"[db-qa] {p['severity']} {p['code']}: {p['message']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps({"stats": stats, "summary": {"errors": errors, "warnings": warnings}, "issues": problems}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[db-qa] JSON report: {args.json_out}")

    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
