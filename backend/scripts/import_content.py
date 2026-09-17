import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app, db
from app.models import Level, Topic, Passage, Question


VALID_SKILLS = {"grammar", "vocabulary", "reading", "listening"}
VALID_QUESTION_TYPES = {
    "multiple_choice",
    "reading_multiple_choice",
    "listening_multiple_choice",
    "reading_comprehension",
    "listening_comprehension",
    "error_identification",
}
VALID_PASSAGE_TYPES = {"reading", "listening"}


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_question(question, owner_code, passage=None):
    required = [
        "code", "skill", "question_type", "difficulty", "prompt",
        "option_a", "option_b", "option_c", "option_d",
        "correct_option", "explanation",
    ]
    missing = [key for key in required if key not in question]
    if missing:
        raise ValueError(f"{owner_code}: question missing fields: {missing}")

    if question["skill"] not in VALID_SKILLS:
        raise ValueError(f"{question['code']}: invalid skill '{question['skill']}'")

    if question["question_type"] not in VALID_QUESTION_TYPES:
        raise ValueError(
            f"{question['code']}: invalid question_type "
            f"'{question['question_type']}'"
        )

    difficulty = int(question["difficulty"])
    if not 1 <= difficulty <= 5:
        raise ValueError(f"{question['code']}: difficulty must be 1-5")

    correct = str(question["correct_option"]).strip().upper()
    if correct not in {"A", "B", "C", "D"}:
        raise ValueError(f"{question['code']}: correct_option must be A-D")

    q_type = question["question_type"]
    if q_type == "listening_multiple_choice" and not question.get("audio_text"):
        raise ValueError(f"{question['code']}: audio_text is required")

    if q_type == "listening_comprehension":
        if passage is None or passage.get("passage_type") != "listening":
            raise ValueError(
                f"{question['code']}: listening_comprehension requires "
                f"a listening passage"
            )


def upsert_level(data):
    code = data["code"].strip().upper()
    level = Level.query.filter_by(code=code).first()
    if not level:
        level = Level(code=code)
        db.session.add(level)

    level.name = data["name"].strip()
    level.description = data.get("description", "").strip()
    level.sort_order = int(data.get("order", 0))
    db.session.flush()
    return level


def upsert_topic(level, data):
    code = data["code"].strip().upper()
    topic = Topic.query.filter_by(code=code).first()

    if not topic:
        topic = Topic(code=code, level_id=level.id, theory="")
        db.session.add(topic)

    topic.level_id = level.id
    topic.sort_order = int(data.get("order", 0))
    topic.title = data["title"].strip()
    topic.objective = data.get("objective", "").strip()
    topic.theory = data.get("theory", "").strip()
    topic.examples = data.get("examples", [])
    topic.common_mistakes = data.get("common_mistakes", [])
    topic.key_vocabulary = data.get("key_vocabulary", [])
    topic.youtube_video_id = data.get("youtube_video_id")
    topic.is_published = bool(data.get("is_published", True))
    db.session.flush()
    return topic


def upsert_passage(topic, data):
    code = data["code"].strip().upper()
    passage_type = data["passage_type"].strip().lower()

    if passage_type not in VALID_PASSAGE_TYPES:
        raise ValueError(f"{code}: invalid passage_type '{passage_type}'")

    passage = Passage.query.filter_by(code=code).first()
    if not passage:
        passage = Passage(
            code=code,
            topic_id=topic.id,
            passage_type=passage_type,
            title=data["title"].strip(),
        )
        db.session.add(passage)

    passage.topic_id = topic.id
    passage.sort_order = int(data.get("order", 0))
    passage.passage_type = passage_type
    passage.title = data["title"].strip()
    passage.instructions = data.get("instructions", "").strip()
    passage.content_text = data.get("content_text")
    passage.audio_text = data.get("audio_text")
    passage.audio_accent = data.get("audio_accent", "en-US")
    passage.audio_rate = float(data.get("audio_rate", 1.0))
    passage.max_audio_plays = int(data.get("max_audio_plays", 2))
    passage.is_active = bool(data.get("is_active", True))

    if passage_type == "reading" and not passage.content_text:
        raise ValueError(f"{code}: reading passage requires content_text")

    if passage_type == "listening" and not passage.audio_text:
        raise ValueError(f"{code}: listening passage requires audio_text")

    db.session.flush()
    return passage


def upsert_question(topic, data, order, passage=None, passage_data=None):
    validate_question(data, topic.code, passage_data)

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
    question.sort_order = int(data.get("order", order))
    question.skill = data["skill"].strip().lower()
    question.question_type = data["question_type"].strip().lower()
    question.difficulty = int(data["difficulty"])
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
    question.is_active = bool(data.get("is_active", True))
    return question


def import_curriculum_file(path):
    data = load_json(path)
    level = upsert_level(data["level"])

    topic_count = 0
    passage_count = 0
    question_count = 0

    for topic_data in data.get("topics", []):
        topic = upsert_topic(level, topic_data)
        topic_count += 1

        for index, question_data in enumerate(topic_data.get("questions", []), 1):
            upsert_question(topic, question_data, index)
            question_count += 1

        for passage_index, passage_data in enumerate(
            topic_data.get("passages", []), 1
        ):
            passage = upsert_passage(topic, passage_data)
            passage_count += 1

            start_order = 100 + (passage_index * 20)
            for q_index, question_data in enumerate(
                passage_data.get("questions", []), 1
            ):
                upsert_question(
                    topic,
                    question_data,
                    start_order + q_index,
                    passage=passage,
                    passage_data=passage_data,
                )
                question_count += 1

    db.session.commit()

    return {
        "level": level.code,
        "topics": topic_count,
        "passages": passage_count,
        "questions": question_count,
    }


def main():
    curriculum_dir = BASE_DIR / "content" / "curriculum"

    if len(sys.argv) > 1:
        requested = Path(sys.argv[1])
        if not requested.is_absolute():
            requested = BASE_DIR / requested
        files = [requested]
    else:
        files = sorted(
            p for p in curriculum_dir.glob("*.json")
            if not p.name.startswith("_")
        )

    if not files:
        print("[import] No curriculum JSON files found.")
        return

    app = create_app()

    with app.app_context():
        total_topics = total_passages = total_questions = 0

        for path in files:
            print(f"[import] Reading {path.name}...")
            try:
                result = import_curriculum_file(path)
            except Exception:
                db.session.rollback()
                raise

            total_topics += result["topics"]
            total_passages += result["passages"]
            total_questions += result["questions"]

            print(
                f"[import] {result['level']}: "
                f"{result['topics']} topics, "
                f"{result['passages']} passages, "
                f"{result['questions']} questions."
            )

        print(
            f"[import] Done. {len(files)} file(s), "
            f"{total_topics} topic(s), "
            f"{total_passages} passage(s), "
            f"{total_questions} question(s)."
        )


if __name__ == "__main__":
    main()
