from __future__ import annotations

import random
import re
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from . import db
from .game_vocabulary import kids_categories, kids_words, serialize_word
from .models import KidsGameRun, KidsWordProgress

kids_bp = Blueprint("kids", __name__, url_prefix="/kids")
THEMES = ["jungle", "space", "ocean", "candy", "rainbow"]
GAMES = {
    "picture_match": {"label": "Picture Match", "icon": "bi-images", "description": "See an English word and tap the matching picture."},
    "listen_tap": {"label": "Listen & Tap", "icon": "bi-volume-up-fill", "description": "Hear a word in English and tap the right picture."},
    "bubble_pop": {"label": "Bubble Pop", "icon": "bi-circle-fill", "description": "Pop the bubble with the right English word."},
    "memory_garden": {"label": "Memory Garden", "icon": "bi-grid-3x3-gap-fill", "description": "Match English words with their pictures."},
    "word_train": {"label": "Word Train", "icon": "bi-train-front-fill", "description": "Put the letters in order to build a simple word."},
    "colors_numbers": {"label": "Colors & Numbers", "icon": "bi-palette-fill", "description": "Play with the first colors and numbers in English."},
}


def _kids_only():
    if not current_user.is_kids_mode and not current_user.is_admin:
        abort(403)


def _owned_run(run_id):
    run = KidsGameRun.query.get_or_404(run_id)
    if run.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return run


def _progress_map(user_id):
    rows = KidsWordProgress.query.filter_by(user_id=user_id).all()
    return {row.word_key: row for row in rows}


def _select_words(user_id, category, game_type, count=8):
    items = kids_words(category=category, game_type=game_type)
    if game_type == "word_train":
        items = [w for w in items if re.fullmatch(r"[A-Za-z'-]{2,14}", w.english or "")]
    progress = _progress_map(user_id)
    random.shuffle(items)
    items.sort(
        key=lambda w: (
            progress.get(w.key).exposures if progress.get(w.key) else 0,
            progress.get(w.key).successes if progress.get(w.key) else 0,
            w.kids_difficulty or 1,
        )
    )
    if len(items) < count:
        extras = [w for w in kids_words(category="all", game_type=game_type) if w.id not in {x.id for x in items}]
        if game_type == "word_train":
            extras = [w for w in extras if re.fullmatch(r"[A-Za-z'-]{2,14}", w.english or "")]
        random.shuffle(extras)
        items.extend(extras)
    return items[:count]


@kids_bp.get("/")
@login_required
def index():
    _kids_only()
    runs = KidsGameRun.query.filter_by(user_id=current_user.id).order_by(KidsGameRun.started_at.desc()).limit(8).all()
    total_stars = sum(row.stars or 0 for row in KidsGameRun.query.filter_by(user_id=current_user.id).all())
    seen_words = KidsWordProgress.query.filter(KidsWordProgress.user_id == current_user.id, KidsWordProgress.exposures > 0).count()
    categories = kids_categories()
    return render_template("kids_index.html", games=GAMES, categories=categories, runs=runs, total_stars=total_stars, seen_words=seen_words)


@kids_bp.get("/play/<string:game_type>")
@login_required
def play(game_type):
    _kids_only()
    if game_type not in GAMES:
        abort(404)
    categories = kids_categories()
    valid_categories = {c[0] for c in categories} | {"all"}
    default_category = categories[0][0] if categories else "all"
    category = request.args.get("category", default_category)
    if category not in valid_categories:
        category = default_category
    return render_template("kids_play.html", game_type=game_type, game=GAMES[game_type], category=category, categories=categories)


@kids_bp.post("/api/start")
@login_required
def start():
    _kids_only()
    payload = request.get_json(silent=True) or {}
    game_type = str(payload.get("game_type") or "")
    categories = kids_categories()
    valid_categories = {c[0] for c in categories} | {"all"}
    default_category = categories[0][0] if categories else "all"
    category = str(payload.get("category") or default_category)
    if game_type not in GAMES:
        return jsonify({"ok": False, "error": "Unknown game."}), 400
    if category not in valid_categories:
        category = default_category

    if game_type == "colors_numbers":
        pool = [w for w in kids_words(category="all", game_type=game_type) if w.category and w.category.code in {"colors", "numbers"}]
        progress = _progress_map(current_user.id)
        random.shuffle(pool)
        pool.sort(key=lambda w: (
            progress.get(w.key).exposures if progress.get(w.key) else 0,
            progress.get(w.key).successes if progress.get(w.key) else 0,
            w.kids_difficulty or 1,
        ))
        selected = pool[:8]
        category = "colors_numbers"
    else:
        selected = _select_words(current_user.id, category, game_type, count=8)

    if len(selected) < 2:
        return jsonify({"ok": False, "error": "This game needs more active vocabulary. Ask the administrator to add words."}), 409

    run = KidsGameRun(
        user_id=current_user.id,
        game_type=game_type,
        category=category,
        theme=THEMES[(KidsGameRun.query.count()) % len(THEMES)],
        stars=0,
        rounds_total=0,
        rounds_success=0,
    )
    db.session.add(run)
    db.session.commit()
    return jsonify({"ok": True, "run_id": run.id, "theme": run.theme, "words": [serialize_word(w) for w in selected]})


@kids_bp.post("/api/run/<int:run_id>/finish")
@login_required
def finish(run_id):
    _kids_only()
    run = _owned_run(run_id)
    if run.completed_at:
        return jsonify({"ok": True, "stars": run.stars})
    payload = request.get_json(silent=True) or {}
    results = payload.get("results") or []
    if not isinstance(results, list):
        return jsonify({"ok": False, "error": "Invalid results."}), 400
    success_count = 0
    total = 0
    valid_keys = {word.key for word in kids_words(category="all")}
    for raw in results[:30]:
        key = str((raw or {}).get("key") or "")
        if not key or key not in valid_keys:
            continue
        total += 1
        success = bool((raw or {}).get("success"))
        success_count += 1 if success else 0
        progress = KidsWordProgress.query.filter_by(user_id=current_user.id, word_key=key).first()
        if not progress:
            progress = KidsWordProgress(user_id=current_user.id, word_key=key, exposures=0, successes=0)
            db.session.add(progress)
        progress.exposures = int(progress.exposures or 0) + 1
        progress.successes = int(progress.successes or 0) + (1 if success else 0)
        progress.last_seen_at = datetime.utcnow()
    run.rounds_total = total
    run.rounds_success = success_count
    run.stars = max(1, min(5, 2 + (success_count // max(1, total // 3)))) if total else 1
    run.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "stars": run.stars, "message": "Great playing!"})
