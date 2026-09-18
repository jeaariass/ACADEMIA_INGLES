from __future__ import annotations

import re
from difflib import SequenceMatcher

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .models import SpeakingAttempt, SpeakingExercise

speaking_bp = Blueprint("speaking", __name__, url_prefix="/speaking")
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _normalize(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^a-z0-9'\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _closed_metrics(expected: str | None, transcript: str):
    if not expected:
        return None, None
    e = _normalize(expected)
    t = _normalize(transcript)
    similarity = round(SequenceMatcher(None, e, t).ratio() * 100, 1) if e and t else 0.0
    expected_tokens = set(e.split())
    transcript_tokens = set(t.split())
    coverage = round(len(expected_tokens & transcript_tokens) / len(expected_tokens) * 100, 1) if expected_tokens else None
    return similarity, coverage


def _target_hits(exercise, transcript):
    normalized = _normalize(transcript)
    hits = 0
    for item in exercise.target_vocabulary or []:
        if _normalize(item) and _normalize(item) in normalized:
            hits += 1
    return hits


@speaking_bp.get("/")
@login_required
def index():
    exercises = SpeakingExercise.query.filter_by(is_published=True).order_by(
        SpeakingExercise.sort_order.asc(), SpeakingExercise.id.asc()
    ).all()
    grouped = {code: [] for code in LEVEL_ORDER}
    for exercise in exercises:
        grouped.setdefault(exercise.level_code, []).append(exercise)
    attempts = SpeakingAttempt.query.filter_by(user_id=current_user.id).count()
    latest = SpeakingAttempt.query.filter_by(user_id=current_user.id).order_by(SpeakingAttempt.created_at.desc()).limit(6).all()
    return render_template("speaking_index.html", grouped=grouped, attempts=attempts, latest=latest)


@speaking_bp.get("/<int:exercise_id>")
@login_required
def practice(exercise_id):
    exercise = SpeakingExercise.query.filter_by(id=exercise_id, is_published=True).first_or_404()
    latest = SpeakingAttempt.query.filter_by(user_id=current_user.id, exercise_id=exercise.id).order_by(SpeakingAttempt.created_at.desc()).first()
    return render_template("speaking_practice.html", exercise=exercise, latest=latest)


@speaking_bp.post("/<int:exercise_id>/attempt")
@login_required
def submit_attempt(exercise_id):
    exercise = SpeakingExercise.query.filter_by(id=exercise_id, is_published=True).first_or_404()
    payload = request.get_json(silent=True) or {}
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"ok": False, "error": "No transcript was captured. Try again or type the transcript manually."}), 400
    if len(transcript) > 6000:
        return jsonify({"ok": False, "error": "Transcript is too long."}), 400

    try:
        confidence = float(payload["confidence"]) if payload.get("confidence") is not None else None
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    try:
        duration = float(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None
    except (TypeError, ValueError):
        duration = None
    if duration is not None:
        duration = max(0.1, min(900.0, duration))

    words = _normalize(transcript).split()
    similarity, coverage = _closed_metrics(exercise.expected_text, transcript)
    wpm = round((len(words) / duration) * 60, 1) if duration and words else None
    target_hits = _target_hits(exercise, transcript)

    attempt = SpeakingAttempt(
        user_id=current_user.id,
        exercise_id=exercise.id,
        transcript=transcript,
        recognition_confidence=confidence,
        duration_seconds=duration,
        similarity_score=similarity,
        token_coverage=coverage,
        words_per_minute=wpm,
        word_count=len(words),
        target_hits=target_hits,
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({
        "ok": True,
        "attempt_id": attempt.id,
        "metrics": {
            "similarity": similarity,
            "coverage": coverage,
            "word_count": len(words),
            "wpm": wpm,
            "target_hits": target_hits,
            "target_total": len(exercise.target_vocabulary or []),
            "confidence_pct": round(confidence * 100, 1) if confidence is not None else None,
        },
        "note": "Speech-recognition confidence and transcript similarity are practice indicators, not a certified pronunciation score.",
    })
