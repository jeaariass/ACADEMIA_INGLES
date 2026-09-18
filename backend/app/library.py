import re
import unicodedata
from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from . import db
from .models import LibraryItem, SavedVocabulary


library_bp = Blueprint("library", __name__, url_prefix="/library")

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
CATEGORY_LABELS = {
    "story": "Story",
    "travel": "Travel",
    "science": "Science",
    "technology": "Technology",
    "society": "Society",
    "news_practice": "News practice",
    "culture": "Culture",
    "academic": "Academic",
}
REVIEW_INTERVAL_DAYS = {
    1: 1,
    2: 3,
    3: 7,
    4: 14,
    5: 30,
    6: 60,
    7: 120,
}


def _normalize_text(value):
    value = unicodedata.normalize("NFKC", (value or "").strip().lower())
    value = re.sub(r"\s+", " ", value)
    return value


def _due_query(user_id):
    return SavedVocabulary.query.filter(
        SavedVocabulary.user_id == user_id,
        SavedVocabulary.translation != "",
        SavedVocabulary.next_review_at <= datetime.utcnow(),
    )


def _library_stats(user_id):
    saved = SavedVocabulary.query.filter_by(user_id=user_id).count()
    due = _due_query(user_id).count()
    mastered = SavedVocabulary.query.filter(
        SavedVocabulary.user_id == user_id,
        SavedVocabulary.mastery_level >= 5,
    ).count()
    return {"saved": saved, "due": due, "mastered": mastered}


@library_bp.route("/")
@login_required
def index():
    level = (request.args.get("level") or "").strip().upper()
    category = (request.args.get("category") or "").strip().lower()
    query_text = (request.args.get("q") or "").strip()[:120]

    query = LibraryItem.query.filter_by(is_published=True)
    if level in LEVEL_ORDER:
        query = query.filter(LibraryItem.level_code == level)
    else:
        level = ""
    if category in CATEGORY_LABELS:
        query = query.filter(LibraryItem.category == category)
    else:
        category = ""
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(
            or_(
                LibraryItem.title.ilike(pattern),
                LibraryItem.summary.ilike(pattern),
                LibraryItem.content_text.ilike(pattern),
            )
        )

    items = query.order_by(
        LibraryItem.level_code.asc(),
        LibraryItem.sort_order.asc(),
        LibraryItem.id.asc(),
    ).all()

    categories = (
        db.session.query(LibraryItem.category, func.count(LibraryItem.id))
        .filter(LibraryItem.is_published.is_(True))
        .group_by(LibraryItem.category)
        .all()
    )

    return render_template(
        "library_index.html",
        items=items,
        levels=LEVEL_ORDER,
        category_labels=CATEGORY_LABELS,
        categories=categories,
        selected_level=level,
        selected_category=category,
        query_text=query_text,
        stats=_library_stats(current_user.id),
    )


@library_bp.route("/item/<int:item_id>")
@login_required
def item(item_id):
    article = LibraryItem.query.filter_by(id=item_id, is_published=True).first_or_404()
    paragraphs = [part.strip() for part in article.content_text.split("\n\n") if part.strip()]
    saved_count = SavedVocabulary.query.filter_by(
        user_id=current_user.id,
        library_item_id=article.id,
    ).count()
    return render_template(
        "library_item.html",
        article=article,
        paragraphs=paragraphs,
        category_label=CATEGORY_LABELS.get(article.category, article.category.title()),
        saved_count=saved_count,
    )


@library_bp.route("/vocabulary")
@login_required
def vocabulary():
    items = (
        SavedVocabulary.query
        .filter_by(user_id=current_user.id)
        .order_by(
            SavedVocabulary.next_review_at.asc(),
            SavedVocabulary.created_at.desc(),
        )
        .all()
    )
    return render_template(
        "vocabulary.html",
        items=items,
        stats=_library_stats(current_user.id),
        now=datetime.utcnow(),
    )


@library_bp.route("/vocabulary/save", methods=["POST"])
@login_required
def save_vocabulary():
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip()
    translation = (data.get("translation") or "").strip()
    context_text = (data.get("context") or "").strip()[:2000]
    notes = (data.get("notes") or "").strip()[:2000]
    article_id = data.get("article_id")

    if not text:
        return jsonify({"ok": False, "error": "Select a word or phrase first."}), 400
    if len(text) > 220:
        return jsonify({"ok": False, "error": "Keep saved selections under 220 characters."}), 400
    if len(translation) > 500:
        return jsonify({"ok": False, "error": "Translation is too long."}), 400

    normalized = _normalize_text(text)
    existing = SavedVocabulary.query.filter_by(
        user_id=current_user.id,
        normalized_text=normalized,
    ).first()

    article = None
    if article_id:
        try:
            article = LibraryItem.query.get(int(article_id))
        except (TypeError, ValueError):
            article = None

    if existing:
        existing.text = text
        if translation:
            existing.translation = translation
        if context_text:
            existing.context_text = context_text
        if notes:
            existing.notes = notes
        if article:
            existing.library_item_id = article.id
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "created": False, "id": existing.id})

    entry = SavedVocabulary(
        user_id=current_user.id,
        library_item_id=article.id if article else None,
        text=text,
        normalized_text=normalized,
        translation=translation,
        context_text=context_text or None,
        notes=notes or None,
        next_review_at=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({"ok": True, "created": True, "id": entry.id})


@library_bp.route("/vocabulary/<int:entry_id>/update", methods=["POST"])
@login_required
def update_vocabulary(entry_id):
    entry = SavedVocabulary.query.filter_by(
        id=entry_id,
        user_id=current_user.id,
    ).first_or_404()
    entry.translation = (request.form.get("translation") or "").strip()[:500]
    entry.notes = (request.form.get("notes") or "").strip()[:2000] or None
    entry.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Vocabulary entry updated.", "success")
    return redirect(url_for("library.vocabulary"))


@library_bp.route("/vocabulary/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_vocabulary(entry_id):
    entry = SavedVocabulary.query.filter_by(
        id=entry_id,
        user_id=current_user.id,
    ).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash("Vocabulary entry removed.", "success")
    return redirect(url_for("library.vocabulary"))


@library_bp.route("/review")
@login_required
def review():
    entry = (
        _due_query(current_user.id)
        .order_by(SavedVocabulary.next_review_at.asc(), SavedVocabulary.id.asc())
        .first()
    )
    due_count = _due_query(current_user.id).count()
    return render_template(
        "vocabulary_review.html",
        entry=entry,
        due_count=due_count,
        stats=_library_stats(current_user.id),
    )


@library_bp.route("/review/<int:entry_id>", methods=["POST"])
@login_required
def review_entry(entry_id):
    entry = SavedVocabulary.query.filter_by(
        id=entry_id,
        user_id=current_user.id,
    ).first_or_404()
    grade = (request.form.get("grade") or "good").strip().lower()
    now = datetime.utcnow()

    if grade == "again":
        entry.incorrect_reviews += 1
        entry.review_stage = max(0, entry.review_stage - 1)
        entry.mastery_level = max(0, entry.mastery_level - 1)
        entry.next_review_at = now + timedelta(minutes=10)
    elif grade == "easy":
        entry.correct_reviews += 1
        entry.review_stage = min(7, entry.review_stage + 2)
        entry.mastery_level = min(5, max(entry.mastery_level, entry.review_stage))
        days = REVIEW_INTERVAL_DAYS.get(entry.review_stage, 120)
        entry.next_review_at = now + timedelta(days=days)
    else:
        entry.correct_reviews += 1
        entry.review_stage = min(7, entry.review_stage + 1)
        entry.mastery_level = min(5, max(entry.mastery_level, entry.review_stage))
        days = REVIEW_INTERVAL_DAYS.get(entry.review_stage, 1)
        entry.next_review_at = now + timedelta(days=days)

    entry.last_reviewed_at = now
    entry.updated_at = now
    db.session.commit()
    return redirect(url_for("library.review"))
