import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app, db
from app.models import Level, Topic, Passage, Question, Assessment, AssessmentQuestion

VALID_SECTIONS = {"grammar", "vocabulary", "reading", "listening", "integrated"}


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def require_topic(topic_code):
    topic = Topic.query.filter_by(code=topic_code).first()
    if not topic:
        raise ValueError(
            f"Topic '{topic_code}' does not exist. Import the curriculum first."
        )
    return topic


def upsert_assessment(data):
    code = data["code"].strip().upper()
    assessment = Assessment.query.filter_by(code=code).first()
    if not assessment:
        assessment = Assessment(
            code=code,
            title=data["title"],
            assessment_type=data["assessment_type"],
        )
        db.session.add(assessment)

    level = None
    if data.get("level_code"):
        level = Level.query.filter_by(code=data["level_code"].strip().upper()).first()
        if not level:
            raise ValueError(f"Level '{data['level_code']}' does not exist.")

    assessment.title = data["title"].strip()
    assessment.assessment_type = data["assessment_type"].strip().lower()
    assessment.level_id = level.id if level else None
    assessment.description = data.get("description", "").strip()
    assessment.instructions = data.get("instructions", "").strip()
    assessment.duration_minutes = data.get("duration_minutes")
    assessment.passing_score = data.get("passing_score")
    assessment.is_adaptive = bool(data.get("is_adaptive", False))
    assessment.is_published = bool(data.get("is_published", False))
    db.session.flush()
    return assessment


def upsert_passage(data):
    topic = require_topic(data["topic_code"])
    code = data["code"].strip().upper()
    passage = Passage.query.filter_by(code=code).first()

    if not passage:
        passage = Passage(
            code=code,
            topic_id=topic.id,
            passage_type=data["passage_type"],
            title=data["title"],
        )
        db.session.add(passage)

    passage.topic_id = topic.id
    passage.sort_order = int(data.get("order", 0))
    passage.passage_type = data["passage_type"].strip().lower()
    passage.title = data["title"].strip()
    passage.instructions = data.get("instructions", "").strip()
    passage.content_text = data.get("content_text")
    passage.audio_text = data.get("audio_text")
    passage.audio_accent = data.get("audio_accent", "en-US")
    passage.audio_rate = float(data.get("audio_rate", 1.0))
    passage.max_audio_plays = int(data.get("max_audio_plays", 2))
    passage.is_active = False
    db.session.flush()
    return passage


def upsert_question(data, passage=None):
    topic = require_topic(data["topic_code"])
    code = data["code"].strip().upper()
    question = Question.query.filter_by(code=code).first()

    if not question:
        question = Question(
            code=code,
            topic_id=topic.id,
            prompt="",
            option_a="",
            option_b="",
            option_c="",
            option_d="",
            correct_option="A",
        )
        db.session.add(question)

    question.topic_id = topic.id
    question.passage_id = passage.id if passage else None
    question.sort_order = int(data.get("order", 0))
    question.skill = data["skill"].strip().lower()
    question.question_type = data["question_type"].strip().lower()
    question.difficulty = int(data.get("difficulty", 1))
    question.prompt = data["prompt"].strip()
    question.option_a = data["option_a"].strip()
    question.option_b = data["option_b"].strip()
    question.option_c = data["option_c"].strip()
    question.option_d = data["option_d"].strip()
    question.correct_option = data["correct_option"].strip().upper()
    question.explanation = data.get("explanation", "").strip()
    question.audio_text = data.get("audio_text")
    question.audio_accent = data.get("audio_accent", "en-US")
    question.audio_rate = float(data.get("audio_rate", 1.0))
    question.max_audio_plays = int(data.get("max_audio_plays", 2))
    question.is_active = False
    db.session.flush()
    return question


def link_question(assessment, question, data):
    section = data["section"].strip().lower()
    if section not in VALID_SECTIONS:
        raise ValueError(f"{question.code}: invalid section '{section}'")

    link = AssessmentQuestion.query.filter_by(
        assessment_id=assessment.id,
        question_id=question.id,
    ).first()

    if not link:
        link = AssessmentQuestion(
            assessment_id=assessment.id,
            question_id=question.id,
        )
        db.session.add(link)

    link.section = section
    link.sort_order = int(data.get("order", 0))
    link.weight = float(data.get("weight", 1.0))
    db.session.flush()
    return link


def import_file(path):
    data = load_json(path)
    assessment = upsert_assessment(data["assessment"])

    expected_ids = set()
    passage_count = 0
    question_count = 0

    for item in data.get("questions", []):
        question = upsert_question(item)
        link_question(assessment, question, item)
        expected_ids.add(question.id)
        question_count += 1

    for passage_data in data.get("passages", []):
        passage = upsert_passage(passage_data)
        passage_count += 1

        for item in passage_data.get("questions", []):
            question = upsert_question(item, passage=passage)
            link_question(assessment, question, item)
            expected_ids.add(question.id)
            question_count += 1

    for link in list(assessment.question_links):
        if link.question_id not in expected_ids:
            db.session.delete(link)

    db.session.commit()
    return assessment, passage_count, question_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_assessment.py content/assessments/A1_level.json")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = BASE_DIR / path

    app = create_app()
    with app.app_context():
        print(f"[assessment-import] Reading {path.name}...")
        try:
            assessment, passages, questions = import_file(path)
        except Exception:
            db.session.rollback()
            raise

        print(
            f"[assessment-import] {assessment.code}: "
            f"{passages} passages, {questions} questions."
        )
        print("[assessment-import] Done.")


if __name__ == "__main__":
    main()
