import random
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import case, func

from . import db
from .learning_plan import ensure_learning_plan, latest_completed_diagnostic
from .game_vocabulary import standard_words, unique_shared_translations
from .models import (
    GameChallenge,
    GameRun,
    Level,
    Question,
    SavedVocabulary,
    Topic,
    TopicProgress,
    UserTopicPlan,
    GameVocabulary,
)


game_bp = Blueprint("game", __name__, url_prefix="/game")

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
VALID_OPTIONS = {"A", "B", "C", "D"}
SCENARIOS = [
    {"key": "meadow", "label": "Green Valley"},
    {"key": "sunset", "label": "Sunset City"},
    {"key": "night", "label": "Moonlight Run"},
    {"key": "coast", "label": "Coastal Route"},
    {"key": "autumn", "label": "Autumn Trail"},
]


def _estimated_level(user_id):
    diagnostic = latest_completed_diagnostic(user_id)
    if diagnostic and diagnostic.estimated_level in LEVEL_ORDER:
        return diagnostic.estimated_level
    return "A1"


def _run_owned(run_id):
    run = GameRun.query.get_or_404(run_id)
    if run.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return run


def _tier_settings(tier):
    tier = max(1, min(int(tier or 1), 12))
    target_difficulty = min(5, 1 + ((tier + 1) // 2))
    return {
        "tier": tier,
        "target_difficulty": target_difficulty,
        "target_distance": 1700 + (min(tier - 1, 9) * 120),
        # Phase 8: the runner feels more dynamic from the first game while
        # obstacles are lower and slightly farther apart.
        "speed_multiplier": round(1.0 + min((tier - 1) * 0.045, 0.40), 2),
        "energy_drain": round(0.40 + min((tier - 1) * 0.04, 0.36), 2),
        "obstacle_gap": max(300, 470 - ((tier - 1) * 16)),
        "challenge_interval": max(340, 470 - ((tier - 1) * 10)),
    }


def _priority_topic_ids(user_id, level_code):
    if ensure_learning_plan(user_id):
        db.session.flush()

    progress_rows = TopicProgress.query.filter_by(user_id=user_id).all()
    completed = {row.topic_id for row in progress_rows if row.completed}

    plan_rows = (
        UserTopicPlan.query
        .join(Topic, Topic.id == UserTopicPlan.topic_id)
        .filter(
            UserTopicPlan.user_id == user_id,
            UserTopicPlan.status.in_(["required", "recommended"]),
        )
        .order_by(
            case(
                (UserTopicPlan.status == "required", 0),
                else_=1,
            ),
            Topic.level_id.asc(),
            Topic.sort_order.asc(),
        )
        .all()
    )

    required_pending = [
        row.topic_id
        for row in plan_rows
        if row.status == "required" and row.topic_id not in completed
    ]
    recommended = [
        row.topic_id
        for row in plan_rows
        if row.status == "recommended" and row.topic_id not in required_pending
    ]
    required_done = [
        row.topic_id
        for row in plan_rows
        if row.status == "required" and row.topic_id in completed
    ]

    ordered = required_pending + recommended + required_done
    if ordered:
        return ordered

    level = Level.query.filter_by(code=level_code).first()
    if not level:
        return []
    return [
        topic.id
        for topic in (
            Topic.query
            .filter_by(level_id=level.id, is_published=True)
            .order_by(Topic.sort_order.asc(), Topic.id.asc())
            .all()
        )
    ]


def _curriculum_question(run):
    used_ids = {
        row.question_id
        for row in run.challenges
        if row.question_id is not None
    }
    priority_ids = _priority_topic_ids(run.user_id, run.level_code)

    base = Question.query.join(Topic, Topic.id == Question.topic_id).filter(
        Question.is_active.is_(True),
        Question.passage_id.is_(None),
        Topic.is_published.is_(True),
    )
    if used_ids:
        base = base.filter(~Question.id.in_(used_ids))

    candidates = []
    if priority_ids:
        candidates = base.filter(Question.topic_id.in_(priority_ids)).all()

    if not candidates:
        level = Level.query.filter_by(code=run.level_code).first()
        if level:
            candidates = base.filter(Topic.level_id == level.id).all()

    if not candidates:
        candidates = base.all()
    if not candidates:
        return None

    priority_rank = {topic_id: index for index, topic_id in enumerate(priority_ids)}
    random.shuffle(candidates)
    target = run.target_difficulty
    candidates.sort(
        key=lambda q: (
            abs((q.level_difficulty or 3) - target),
            priority_rank.get(q.topic_id, 9999),
        )
    )
    return candidates[0]


def _vocabulary_challenge(run):
    used_ids = {
        row.saved_vocabulary_id
        for row in run.challenges
        if row.saved_vocabulary_id is not None
    }
    query = SavedVocabulary.query.filter(
        SavedVocabulary.user_id == run.user_id,
        SavedVocabulary.translation != "",
    )
    if used_ids:
        query = query.filter(~SavedVocabulary.id.in_(used_ids))

    candidates = query.order_by(
        SavedVocabulary.mastery_level.asc(),
        SavedVocabulary.next_review_at.asc(),
        SavedVocabulary.id.asc(),
    ).all()
    if not candidates:
        return None

    all_vocab = SavedVocabulary.query.filter(
        SavedVocabulary.user_id == run.user_id,
        SavedVocabulary.translation != "",
    ).all()
    unique_translations = []
    for item in all_vocab:
        value = (item.translation or "").strip()
        if value and value.lower() not in {x.lower() for x in unique_translations}:
            unique_translations.append(value)
    if len(unique_translations) < 4:
        return None

    entry = candidates[0]
    correct = entry.translation.strip()
    distractors = [
        value for value in unique_translations
        if value.lower() != correct.lower()
    ]
    random.shuffle(distractors)
    options = [correct] + distractors[:3]
    random.shuffle(options)
    correct_option = "ABCD"[options.index(correct)]

    return {
        "entry": entry,
        "prompt": f'What is the best Spanish translation of “{entry.text}”?',
        "options": options,
        "correct_option": correct_option,
        "explanation": entry.context_text or "Review this expression in your personal vocabulary bank.",
        "difficulty": max(1, min(5, 1 + (entry.mastery_level or 0))),
        "skill": "vocabulary",
        "source_label": "My Vocabulary",
    }



def _shared_vocabulary_challenge(run):
    used_ids = {row.game_vocabulary_id for row in run.challenges if getattr(row, "game_vocabulary_id", None)}
    candidates = [row for row in standard_words(run.level_code, game_type="word_runner") if row.id not in used_ids]
    if not candidates:
        return None
    # Keep the runner close to the current tier's target difficulty.
    candidates.sort(key=lambda row: abs((row.standard_difficulty or 1) - (run.target_difficulty or 1)))
    entry = candidates[0]
    distractors = unique_shared_translations(run.level_code, correct=entry.spanish, game_type="word_runner")[:3]
    if len(distractors) < 3:
        return None
    options = [entry.spanish] + distractors
    random.shuffle(options)
    return {
        "entry": entry,
        "prompt": f'What is the best Spanish translation of “{entry.english}”?',
        "options": options,
        "correct_option": "ABCD"[options.index(entry.spanish)],
        "explanation": f'{entry.english} = {entry.spanish}',
        "difficulty": entry.standard_difficulty or 1,
        "skill": "vocabulary",
        "source_label": "Game Vocabulary",
    }

def _serialize_challenge(challenge):
    return {
        "id": challenge.id,
        "prompt": challenge.prompt,
        "options": {
            "A": challenge.option_a,
            "B": challenge.option_b,
            "C": challenge.option_c,
            "D": challenge.option_d,
        },
        "difficulty": challenge.difficulty,
        "skill": challenge.skill,
        "source": challenge.source_label,
    }


@game_bp.route("/")
@login_required
def index():
    completed = GameRun.query.filter_by(
        user_id=current_user.id,
        status="completed",
    ).count()
    best_score = (
        db.session.query(func.max(GameRun.score))
        .filter(GameRun.user_id == current_user.id)
        .scalar()
        or 0
    )
    best_distance = (
        db.session.query(func.max(GameRun.distance))
        .filter(GameRun.user_id == current_user.id)
        .scalar()
        or 0
    )
    recent = (
        GameRun.query
        .filter_by(user_id=current_user.id)
        .order_by(GameRun.started_at.desc(), GameRun.id.desc())
        .limit(8)
        .all()
    )
    vocab_count = SavedVocabulary.query.filter(
        SavedVocabulary.user_id == current_user.id,
        SavedVocabulary.translation != "",
    ).count()
    shared_vocab_count = len(standard_words(_estimated_level(current_user.id), game_type="word_runner"))
    next_settings = _tier_settings(completed + 1)
    return render_template(
        "game_index.html",
        completed_runs=completed,
        best_score=best_score,
        best_distance=int(best_distance),
        recent_runs=recent,
        estimated_level=_estimated_level(current_user.id),
        vocab_count=vocab_count,
        shared_vocab_count=shared_vocab_count,
        next_settings=next_settings,
    )


@game_bp.route("/play")
@login_required
def play():
    return render_template("game_play.html")


@game_bp.route("/api/run/start", methods=["POST"])
@login_required
def start_run():
    # A new run closes any abandoned browser session cleanly.
    stale = GameRun.query.filter_by(
        user_id=current_user.id,
        status="in_progress",
    ).all()
    for item in stale:
        item.status = "abandoned"
        item.completed_at = datetime.utcnow()

    completed = GameRun.query.filter_by(
        user_id=current_user.id,
        status="completed",
    ).count()
    settings = _tier_settings(completed + 1)
    run = GameRun(
        user_id=current_user.id,
        difficulty_tier=settings["tier"],
        completion_number=completed + 1,
        target_distance=settings["target_distance"],
        target_difficulty=settings["target_difficulty"],
        level_code=_estimated_level(current_user.id),
        status="in_progress",
    )
    db.session.add(run)
    db.session.flush()
    # Rotate scenarios by run id so consecutive games always change scenery,
    # even when the previous run was failed or abandoned.
    scenario = SCENARIOS[(run.id - 1) % len(SCENARIOS)]
    db.session.commit()

    return jsonify({
        "ok": True,
        "run_id": run.id,
        "level_code": run.level_code,
        "scenario": scenario,
        **settings,
    })


@game_bp.route("/api/run/<int:run_id>/challenge", methods=["POST"])
@login_required
def create_challenge(run_id):
    run = _run_owned(run_id)
    if run.status != "in_progress":
        return jsonify({"ok": False, "error": "This run is no longer active."}), 409

    answered_or_open = len(run.challenges)
    vocab = None
    shared_vocab = None
    # Rotate personal and administrator-managed vocabulary through the runner.
    if answered_or_open % 3 == 1:
        shared_vocab = _shared_vocabulary_challenge(run)
    elif answered_or_open % 3 == 2:
        vocab = _vocabulary_challenge(run)

    if shared_vocab:
        options = shared_vocab["options"]
        challenge = GameChallenge(
            game_run_id=run.id,
            game_vocabulary_id=shared_vocab["entry"].id,
            source_type="shared_vocabulary",
            source_label=shared_vocab["source_label"],
            skill=shared_vocab["skill"],
            prompt=shared_vocab["prompt"],
            option_a=options[0],
            option_b=options[1],
            option_c=options[2],
            option_d=options[3],
            correct_option=shared_vocab["correct_option"],
            explanation=shared_vocab["explanation"],
            difficulty=shared_vocab["difficulty"],
        )
    elif vocab:
        options = vocab["options"]
        challenge = GameChallenge(
            game_run_id=run.id,
            saved_vocabulary_id=vocab["entry"].id,
            source_type="vocabulary",
            source_label=vocab["source_label"],
            skill=vocab["skill"],
            prompt=vocab["prompt"],
            option_a=options[0],
            option_b=options[1],
            option_c=options[2],
            option_d=options[3],
            correct_option=vocab["correct_option"],
            explanation=vocab["explanation"],
            difficulty=vocab["difficulty"],
        )
    else:
        question = _curriculum_question(run)
        if not question:
            return jsonify({"ok": False, "error": "No practice questions are available."}), 404
        challenge = GameChallenge(
            game_run_id=run.id,
            question_id=question.id,
            source_type="curriculum",
            source_label=(
                f"{question.topic.level.code} · {question.topic.title}"
                if question.topic and question.topic.level
                else "Curriculum"
            ),
            skill=question.skill or "grammar",
            prompt=question.prompt,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_option=question.correct_option,
            explanation=question.explanation or "Review the linked lesson for more detail.",
            difficulty=question.level_difficulty or 3,
        )

    db.session.add(challenge)
    db.session.commit()
    return jsonify({"ok": True, "challenge": _serialize_challenge(challenge)})


@game_bp.route("/api/run/<int:run_id>/challenge/<int:challenge_id>/answer", methods=["POST"])
@login_required
def answer_challenge(run_id, challenge_id):
    run = _run_owned(run_id)
    challenge = GameChallenge.query.filter_by(
        id=challenge_id,
        game_run_id=run.id,
    ).first_or_404()
    if run.status != "in_progress":
        return jsonify({"ok": False, "error": "This run is no longer active."}), 409
    if challenge.answered_at is not None:
        return jsonify({"ok": False, "error": "This challenge was already answered."}), 409

    data = request.get_json(silent=True) or {}
    selected = (data.get("selected_option") or "").strip().upper()
    if selected not in VALID_OPTIONS:
        return jsonify({"ok": False, "error": "Choose A, B, C or D."}), 400

    correct = selected == challenge.correct_option
    challenge.selected_option = selected
    challenge.is_correct = correct
    challenge.answered_at = datetime.utcnow()

    run.questions_answered += 1
    if correct:
        run.correct_answers += 1
        score_delta = 90 + (challenge.difficulty * 15)
        energy_delta = 24 + (challenge.difficulty * 2)
        run.score += score_delta
    else:
        score_delta = 0
        energy_delta = -8

    db.session.commit()
    return jsonify({
        "ok": True,
        "correct": correct,
        "correct_option": challenge.correct_option,
        "explanation": challenge.explanation,
        "energy_delta": energy_delta,
        "score_delta": score_delta,
        "score": run.score,
        "questions_answered": run.questions_answered,
        "correct_answers": run.correct_answers,
    })


@game_bp.route("/api/run/<int:run_id>/finish", methods=["POST"])
@login_required
def finish_run(run_id):
    run = _run_owned(run_id)
    if run.status != "in_progress":
        return jsonify({"ok": True, "status": run.status, "score": run.score})

    data = request.get_json(silent=True) or {}
    try:
        distance = max(0.0, float(data.get("distance", 0)))
        energy = max(0.0, min(100.0, float(data.get("energy", 0))))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid game result."}), 400

    requested_status = (data.get("status") or "failed").strip().lower()
    completed = requested_status == "completed" and distance >= (run.target_distance * 0.98)

    run.distance = round(distance, 1)
    run.energy_end = round(energy, 1)
    run.status = "completed" if completed else "failed"
    run.completed_at = datetime.utcnow()
    run.score += int(min(distance, run.target_distance) // 10)
    db.session.commit()

    completed_total = GameRun.query.filter_by(
        user_id=run.user_id,
        status="completed",
    ).count()
    return jsonify({
        "ok": True,
        "status": run.status,
        "score": run.score,
        "distance": run.distance,
        "correct": run.correct_answers,
        "questions": run.questions_answered,
        "next_tier": min(12, completed_total + 1),
    })
