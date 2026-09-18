from __future__ import annotations

import random
import re
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .learning_plan import latest_completed_diagnostic
from .models import ArcadeChallenge, ArcadeRun, Question, SavedVocabulary, SpeakingExercise
from .game_vocabulary import standard_words, unique_shared_translations

arcade_bp = Blueprint("arcade", __name__, url_prefix="/arcade")
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
GAME_TYPES = {
    "vocabulary_blitz": {"label": "Vocabulary Blitz", "icon": "bi-lightning-charge-fill", "rounds": 10, "description": "Fast English ↔ Spanish vocabulary choices."},
    "grammar_target": {"label": "Grammar Target", "icon": "bi-bullseye", "rounds": 10, "description": "Hit the correct grammar option before the timer runs out."},
    "listening_sprint": {"label": "Listening Sprint", "icon": "bi-headphones", "rounds": 8, "description": "Listen once, understand the prompt, choose quickly."},
    "word_scramble": {"label": "Word Scramble", "icon": "bi-shuffle", "rounds": 8, "description": "Rebuild useful words from shuffled letters."},
    "sentence_builder": {"label": "Sentence Builder", "icon": "bi-bricks", "rounds": 8, "description": "Put the words back into a correct English sentence."},
    "memory_match": {"label": "Memory Match", "icon": "bi-grid-3x3-gap-fill", "rounds": 8, "description": "Match English words with their Spanish meanings."},
}


def _level_code(user_id):
    diagnostic = latest_completed_diagnostic(user_id)
    if diagnostic and diagnostic.estimated_level in LEVEL_ORDER:
        return diagnostic.estimated_level
    return "A1"


def _owned_run(run_id):
    run = ArcadeRun.query.get_or_404(run_id)
    if run.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return run


def _options(question):
    return [question.option_a, question.option_b, question.option_c, question.option_d]


def _question_candidate(user_id, skill, level_code, used_ids):
    query = Question.query.filter(Question.is_active.is_(True), Question.skill == skill)
    if used_ids:
        query = query.filter(~Question.id.in_(used_ids))
    candidates = query.all()
    level_candidates = [q for q in candidates if q.topic and q.topic.level and q.topic.level.code == level_code]
    return random.choice(level_candidates or candidates) if (level_candidates or candidates) else None


def _vocab_candidate(user_id, used_ids, single_word=False):
    query = SavedVocabulary.query.filter(
        SavedVocabulary.user_id == user_id,
        SavedVocabulary.translation != "",
    )
    if used_ids:
        query = query.filter(~SavedVocabulary.id.in_(used_ids))
    rows = query.order_by(SavedVocabulary.mastery_level.asc(), SavedVocabulary.next_review_at.asc()).all()
    if single_word:
        rows = [r for r in rows if re.fullmatch(r"[A-Za-z'-]{3,18}", r.text or "")]
    return random.choice(rows[:12]) if rows else None


def _unique_vocab_options(user_id, correct):
    rows = SavedVocabulary.query.filter(SavedVocabulary.user_id == user_id, SavedVocabulary.translation != "").all()
    vals = []
    for row in rows:
        value = (row.translation or "").strip()
        if value and value.lower() != correct.lower() and value.lower() not in {x.lower() for x in vals}:
            vals.append(value)
    random.shuffle(vals)
    return vals[:3]



def _shared_vocab_candidate(level_code, game_type, used_ids=None, single_word=False):
    used_ids = used_ids or set()
    rows = [row for row in standard_words(level_code, game_type=game_type, single_word=single_word) if row.id not in used_ids]
    return rows[0] if rows else None


def _shared_vocab_options(level_code, game_type, correct):
    vals = unique_shared_translations(level_code, correct=correct, game_type=game_type)
    return vals[:3]

def _create_challenge(run):
    used_questions = {c.source_id for c in run.challenges if c.source_type == "question" and c.source_id}
    used_vocab = {c.source_id for c in run.challenges if c.source_type == "vocabulary" and c.source_id}
    used_shared = {c.source_id for c in run.challenges if c.source_type == "shared_vocabulary" and c.source_id}
    game = run.game_type
    round_number = len(run.challenges)

    if game == "vocabulary_blitz":
        # Alternate the personal bank and the administrator-managed shared bank.
        if round_number % 2 == 0:
            shared = _shared_vocab_candidate(run.level_code, game, used_shared)
            if shared:
                distractors = _shared_vocab_options(run.level_code, game, shared.spanish)
                if len(distractors) == 3:
                    options = [shared.spanish] + distractors
                    random.shuffle(options)
                    return ArcadeChallenge(
                        arcade_run_id=run.id, source_type="shared_vocabulary", source_id=shared.id,
                        prompt=f'Choose the best Spanish meaning of “{shared.english}”.',
                        payload={"kind":"multiple_choice", "options":options, "source":"Game Vocabulary"},
                        correct_answer=shared.spanish,
                    )
        vocab = _vocab_candidate(run.user_id, used_vocab)
        if vocab:
            distractors = _unique_vocab_options(run.user_id, vocab.translation)
            if len(distractors) == 3:
                options = [vocab.translation] + distractors
                random.shuffle(options)
                return ArcadeChallenge(
                    arcade_run_id=run.id, source_type="vocabulary", source_id=vocab.id,
                    prompt=f'Choose the best Spanish meaning of “{vocab.text}”.',
                    payload={"kind":"multiple_choice", "options":options, "source":"My Vocabulary"},
                    correct_answer=vocab.translation,
                )
        shared = _shared_vocab_candidate(run.level_code, game, used_shared)
        if shared:
            distractors = _shared_vocab_options(run.level_code, game, shared.spanish)
            if len(distractors) == 3:
                options=[shared.spanish]+distractors; random.shuffle(options)
                return ArcadeChallenge(arcade_run_id=run.id, source_type="shared_vocabulary", source_id=shared.id, prompt=f'Choose the best Spanish meaning of “{shared.english}”.', payload={"kind":"multiple_choice","options":options,"source":"Game Vocabulary"}, correct_answer=shared.spanish)
        q = _question_candidate(run.user_id, "vocabulary", run.level_code, used_questions)
        if q:
            return ArcadeChallenge(arcade_run_id=run.id, source_type="question", source_id=q.id, prompt=q.prompt, payload={"kind":"multiple_choice","options":_options(q),"source":"Curriculum"}, correct_answer=getattr(q, f"option_{q.correct_option.lower()}"))

    if game == "grammar_target":
        q = _question_candidate(run.user_id, "grammar", run.level_code, used_questions)
        if q:
            return ArcadeChallenge(arcade_run_id=run.id, source_type="question", source_id=q.id, prompt=q.prompt, payload={"kind":"multiple_choice","options":_options(q),"source":q.topic.title if q.topic else "Grammar"}, correct_answer=getattr(q, f"option_{q.correct_option.lower()}"))

    if game == "listening_sprint":
        # Every other round can be administrator-managed vocabulary spoken by TTS.
        if round_number % 2 == 0:
            shared = _shared_vocab_candidate(run.level_code, game, used_shared)
            if shared:
                distractors = _shared_vocab_options(run.level_code, game, shared.spanish)
                if len(distractors) == 3:
                    options=[shared.spanish]+distractors; random.shuffle(options)
                    return ArcadeChallenge(arcade_run_id=run.id, source_type="shared_vocabulary", source_id=shared.id, prompt="Listen and choose the Spanish meaning.", payload={"kind":"listening","options":options,"audio_text":shared.english,"audio_rate":0.92,"source":"Game Vocabulary"}, correct_answer=shared.spanish)
        q = _question_candidate(run.user_id, "listening", run.level_code, used_questions)
        if q:
            audio = q.audio_text or (q.passage.audio_text if q.passage else None) or q.prompt
            return ArcadeChallenge(arcade_run_id=run.id, source_type="question", source_id=q.id, prompt=q.prompt, payload={"kind":"listening","options":_options(q),"audio_text":audio,"audio_rate":(q.passage.audio_rate if q.passage else q.audio_rate or 1.0),"source":"Listening"}, correct_answer=getattr(q, f"option_{q.correct_option.lower()}"))

    if game == "word_scramble":
        if round_number % 2 == 0:
            shared = _shared_vocab_candidate(run.level_code, game, used_shared, single_word=True)
            if shared:
                letters=list(shared.english.lower())
                for _ in range(8):
                    random.shuffle(letters)
                    if "".join(letters) != shared.english.lower(): break
                return ArcadeChallenge(arcade_run_id=run.id, source_type="shared_vocabulary", source_id=shared.id, prompt=f"Unscramble this word: {' '.join(letters).upper()}", payload={"kind":"text","hint":shared.spanish,"source":"Game Vocabulary"}, correct_answer=shared.english.lower())
        vocab = _vocab_candidate(run.user_id, used_vocab, single_word=True)
        if vocab:
            letters = list(vocab.text.lower())
            for _ in range(8):
                random.shuffle(letters)
                if "".join(letters) != vocab.text.lower(): break
            return ArcadeChallenge(arcade_run_id=run.id, source_type="vocabulary", source_id=vocab.id, prompt=f"Unscramble this word: {' '.join(letters).upper()}", payload={"kind":"text","hint":vocab.translation,"source":"My Vocabulary"}, correct_answer=vocab.text.lower())
        shared = _shared_vocab_candidate(run.level_code, game, used_shared, single_word=True)
        if shared:
            letters=list(shared.english.lower()); random.shuffle(letters)
            return ArcadeChallenge(arcade_run_id=run.id, source_type="shared_vocabulary", source_id=shared.id, prompt=f"Unscramble this word: {' '.join(letters).upper()}", payload={"kind":"text","hint":shared.spanish,"source":"Game Vocabulary"}, correct_answer=shared.english.lower())
        q = _question_candidate(run.user_id, "vocabulary", run.level_code, used_questions)
        if q:
            answer = getattr(q, f"option_{q.correct_option.lower()}").strip()
            if re.fullmatch(r"[A-Za-z'-]{3,18}", answer):
                letters=list(answer.lower()); random.shuffle(letters)
                return ArcadeChallenge(arcade_run_id=run.id, source_type="question", source_id=q.id, prompt=f"Unscramble this English word: {' '.join(letters).upper()}", payload={"kind":"text","hint":q.prompt,"source":"Curriculum"}, correct_answer=answer.lower())

    if game == "sentence_builder":
        candidates = SpeakingExercise.query.filter(SpeakingExercise.is_published.is_(True), SpeakingExercise.expected_text.isnot(None)).all()
        level_rows = [x for x in candidates if x.level_code == run.level_code]
        rows = level_rows or candidates
        if rows:
            ex = random.choice(rows)
            sentence = ex.expected_text.strip(); words = sentence.split(); shuffled = words[:]
            for _ in range(8):
                random.shuffle(shuffled)
                if shuffled != words: break
            return ArcadeChallenge(arcade_run_id=run.id, source_type="speaking_sentence", source_id=ex.id, prompt="Build the sentence in the correct order.", payload={"kind":"builder","words":shuffled,"source":ex.title}, correct_answer=sentence)
    return None


@arcade_bp.get("/")
@login_required
def index():
    recent = ArcadeRun.query.filter_by(user_id=current_user.id).order_by(ArcadeRun.started_at.desc()).limit(8).all()
    best = dict(db.session.query(ArcadeRun.game_type, func.max(ArcadeRun.score)).filter(ArcadeRun.user_id == current_user.id, ArcadeRun.status == "completed").group_by(ArcadeRun.game_type).all())
    return render_template("arcade_index.html", games=GAME_TYPES, recent=recent, best=best)


@arcade_bp.get("/<string:game_type>")
@login_required
def play(game_type):
    if game_type not in GAME_TYPES:
        abort(404)
    return render_template("arcade_play.html", game_type=game_type, game=GAME_TYPES[game_type])


@arcade_bp.post("/api/start")
@login_required
def start():
    payload = request.get_json(silent=True) or {}
    game_type = str(payload.get("game_type") or "")
    if game_type not in GAME_TYPES:
        return jsonify({"ok":False,"error":"Unknown game."}), 400
    run = ArcadeRun(user_id=current_user.id, game_type=game_type, level_code=_level_code(current_user.id), status="in_progress")
    db.session.add(run); db.session.flush()

    response = {"ok":True,"run_id":run.id,"round_limit":GAME_TYPES[game_type]["rounds"],"level_code":run.level_code}
    if game_type == "memory_match":
        rows = SavedVocabulary.query.filter(SavedVocabulary.user_id == current_user.id, SavedVocabulary.translation != "").order_by(SavedVocabulary.mastery_level.asc()).limit(20).all()
        pairs=[]; seen=set()
        for row in rows:
            key=((row.text or "").strip().lower(),(row.translation or "").strip().lower())
            if not key[0] or not key[1] or key in seen: continue
            seen.add(key); pairs.append({"id":f"personal-{row.id}","en":row.text,"es":row.translation,"source":"My Vocabulary"})
            if len(pairs)>=8: break
        for row in standard_words(response["level_code"], game_type="memory_match"):
            key=((row.english or "").strip().lower(),(row.spanish or "").strip().lower())
            if not key[0] or not key[1] or key in seen: continue
            seen.add(key); pairs.append({"id":f"shared-{row.id}","en":row.english,"es":row.spanish,"source":"Game Vocabulary"})
            if len(pairs)>=8: break
        if len(pairs)<4:
            db.session.rollback()
            return jsonify({"ok":False,"error":"Memory Match needs at least 4 vocabulary pairs. Add them in Admin → Game Vocabulary."}), 400
        response["pairs"]=pairs
    db.session.commit()
    return jsonify(response)


@arcade_bp.post("/api/run/<int:run_id>/challenge")
@login_required
def challenge(run_id):
    run=_owned_run(run_id)
    if run.status != "in_progress" or run.game_type == "memory_match":
        return jsonify({"ok":False,"error":"No challenge available."}), 400
    unanswered = next((c for c in run.challenges if c.selected_answer is None), None)
    challenge = unanswered or _create_challenge(run)
    if not challenge:
        return jsonify({"ok":False,"error":"Not enough content is available for another round."}), 409
    if challenge.id is None:
        db.session.add(challenge); db.session.commit()
    return jsonify({"ok":True,"challenge":{"id":challenge.id,"prompt":challenge.prompt,"payload":challenge.payload}})


@arcade_bp.post("/api/run/<int:run_id>/challenge/<int:challenge_id>/answer")
@login_required
def answer(run_id, challenge_id):
    run=_owned_run(run_id)
    challenge=ArcadeChallenge.query.filter_by(id=challenge_id, arcade_run_id=run.id).first_or_404()
    if challenge.selected_answer is not None:
        return jsonify({"ok":False,"error":"Round already answered."}), 409
    payload=request.get_json(silent=True) or {}
    selected=str(payload.get("answer") or "").strip()
    if not selected:
        return jsonify({"ok":False,"error":"Answer required."}),400
    expected=challenge.correct_answer.strip()
    is_correct=selected.casefold()==expected.casefold()
    challenge.selected_answer=selected
    challenge.is_correct=is_correct
    challenge.answered_at=datetime.utcnow()
    run.rounds_total += 1
    if is_correct:
        run.rounds_correct += 1
        run.score += 100
    else:
        run.score += 10
    db.session.commit()
    return jsonify({"ok":True,"correct":is_correct,"correct_answer":expected,"score":run.score,"rounds_total":run.rounds_total,"rounds_correct":run.rounds_correct})


@arcade_bp.post("/api/run/<int:run_id>/finish")
@login_required
def finish(run_id):
    run=_owned_run(run_id)
    if run.status != "in_progress":
        return jsonify({"ok":True,"score":run.score})
    payload=request.get_json(silent=True) or {}
    if run.game_type == "memory_match":
        try:
            total=max(0,min(20,int(payload.get("rounds_total",0))))
            correct=max(0,min(total,int(payload.get("rounds_correct",0))))
            score=max(0,min(100000,int(payload.get("score",correct*100))))
        except (TypeError,ValueError):
            return jsonify({"ok":False,"error":"Invalid game summary."}),400
        run.rounds_total=total; run.rounds_correct=correct; run.score=score
    run.status="completed"; run.completed_at=datetime.utcnow(); db.session.commit()
    return jsonify({"ok":True,"score":run.score,"rounds_total":run.rounds_total,"rounds_correct":run.rounds_correct})
