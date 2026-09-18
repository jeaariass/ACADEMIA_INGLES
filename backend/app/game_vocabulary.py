from __future__ import annotations

import json
import random
from pathlib import Path

from sqlalchemy import or_

from . import db
from .models import GameVocabulary, GameVocabularyCategory

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
KIDS_GAMES = {
    "picture_match",
    "listen_tap",
    "bubble_pop",
    "memory_garden",
    "word_train",
    "colors_numbers",
}
ARCADE_GAMES = {
    "vocabulary_blitz",
    "listening_sprint",
    "word_scramble",
    "memory_match",
    "word_runner",
}
STARTER_CATEGORIES = [
    ("first_words", "First words", "👋"),
    ("animals", "Animals", "🐶"),
    ("colors", "Colors", "🌈"),
    ("numbers", "Numbers", "🔢"),
    ("food", "Food", "🍎"),
    ("family", "Family", "👨‍👩‍👧"),
    ("body", "Body", "✋"),
    ("school", "School", "🎒"),
    ("home", "Home", "🏠"),
    ("nature", "Nature", "🌳"),
]
STARTER_PATH = Path(__file__).resolve().parents[1] / "content" / "kids" / "basic_vocabulary.json"


def normalize_code(value, max_length=80):
    value = (value or "").strip().lower().replace(" ", "_")
    value = "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"})
    return value[:max_length]


def normalize_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "y", "x", "on", "activo"}


def normalize_games(value, allowed):
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        text = str(value).strip()
        if not text or text.upper() in {"ALL", "TODOS", "*"}:
            return []
        raw = text.replace("|", ";").replace(",", ";").split(";")
    out = []
    for item in raw:
        key = normalize_code(item, 50)
        if key in allowed and key not in out:
            out.append(key)
    return out


def game_allowed(configured, game_type):
    configured = configured or []
    return not configured or game_type in configured


def serialize_word(word):
    return {
        "id": word.id,
        "key": word.key,
        "en": word.english,
        "es": word.spanish,
        "emoji": word.visual,
        "visual": word.visual,
        "category": word.category.code if word.category else "",
        "kids_difficulty": word.kids_difficulty,
        "cefr_level": word.cefr_level,
        "standard_difficulty": word.standard_difficulty,
    }


def kids_categories():
    rows = (
        GameVocabularyCategory.query
        .filter(
            GameVocabularyCategory.is_active.is_(True),
            GameVocabularyCategory.kids_enabled.is_(True),
        )
        .order_by(GameVocabularyCategory.sort_order.asc(), GameVocabularyCategory.name.asc())
        .all()
    )
    result = []
    for row in rows:
        count = (
            GameVocabulary.query
            .filter_by(category_id=row.id, is_active=True, kids_enabled=True)
            .count()
        )
        if count:
            result.append((row.code, row.name, row.visual or "🎮"))
    return result


def kids_words(category=None, game_type=None):
    query = (
        GameVocabulary.query
        .join(GameVocabularyCategory, GameVocabularyCategory.id == GameVocabulary.category_id)
        .filter(
            GameVocabulary.is_active.is_(True),
            GameVocabulary.kids_enabled.is_(True),
            GameVocabularyCategory.is_active.is_(True),
            GameVocabularyCategory.kids_enabled.is_(True),
        )
    )
    if category and category != "all":
        query = query.filter(GameVocabularyCategory.code == category)
    rows = query.order_by(GameVocabulary.kids_difficulty.asc(), GameVocabulary.sort_order.asc(), GameVocabulary.id.asc()).all()
    if game_type:
        rows = [row for row in rows if game_allowed(row.kids_games, game_type)]
    return rows


def standard_words(level_code="A1", game_type=None, single_word=False):
    max_rank = LEVEL_ORDER.index(level_code) if level_code in LEVEL_ORDER else 0
    allowed_levels = LEVEL_ORDER[: max_rank + 1]
    rows = (
        GameVocabulary.query
        .join(GameVocabularyCategory, GameVocabularyCategory.id == GameVocabulary.category_id)
        .filter(
            GameVocabulary.is_active.is_(True),
            GameVocabulary.standard_enabled.is_(True),
            GameVocabularyCategory.is_active.is_(True),
            GameVocabularyCategory.standard_enabled.is_(True),
            GameVocabulary.cefr_level.in_(allowed_levels),
        )
        .order_by(GameVocabulary.standard_difficulty.asc(), GameVocabulary.sort_order.asc(), GameVocabulary.id.asc())
        .all()
    )
    if game_type:
        rows = [row for row in rows if game_allowed(row.arcade_games, game_type)]
    if single_word:
        import re
        rows = [row for row in rows if re.fullmatch(r"[A-Za-z'-]{2,24}", row.english or "")]
    exact = [row for row in rows if row.cefr_level == level_code]
    lower = [row for row in rows if row.cefr_level != level_code]
    random.shuffle(exact)
    random.shuffle(lower)
    return exact + lower


def unique_shared_translations(level_code, correct=None, game_type=None):
    vals = []
    for row in standard_words(level_code, game_type=game_type):
        value = (row.spanish or "").strip()
        if not value:
            continue
        if correct and value.casefold() == correct.casefold():
            continue
        if value.casefold() not in {x.casefold() for x in vals}:
            vals.append(value)
    random.shuffle(vals)
    return vals


def seed_game_vocabulary():
    """Create starter categories/words once. Admin changes survive restarts."""
    category_map = {}
    for order, (code, name, visual) in enumerate(STARTER_CATEGORIES, start=1):
        row = GameVocabularyCategory.query.filter_by(code=code).first()
        if not row:
            row = GameVocabularyCategory(
                code=code,
                name=name,
                visual=visual,
                sort_order=order,
                kids_enabled=True,
                standard_enabled=True,
                is_active=True,
            )
            db.session.add(row)
            db.session.flush()
        category_map[code] = row

    if not STARTER_PATH.exists():
        return 0
    data = json.loads(STARTER_PATH.read_text(encoding="utf-8"))
    created = 0
    for order, raw in enumerate(data, start=1):
        key = normalize_code(raw.get("key"), 80)
        if not key or GameVocabulary.query.filter_by(key=key).first():
            continue
        category_code = normalize_code(raw.get("category"), 60) or "first_words"
        category = category_map.get(category_code)
        if not category:
            category = GameVocabularyCategory(
                code=category_code,
                name=category_code.replace("_", " ").title(),
                visual="🎮",
                sort_order=100 + order,
                kids_enabled=True,
                standard_enabled=True,
                is_active=True,
            )
            db.session.add(category)
            db.session.flush()
            category_map[category_code] = category
        db.session.add(GameVocabulary(
            key=key,
            category_id=category.id,
            english=(raw.get("en") or "").strip(),
            spanish=(raw.get("es") or "").strip(),
            visual=(raw.get("emoji") or "✨").strip(),
            kids_difficulty=1,
            cefr_level="A1",
            standard_difficulty=1,
            kids_enabled=True,
            standard_enabled=True,
            kids_games=[],
            arcade_games=[],
            sort_order=order,
            is_active=True,
        ))
        created += 1
    return created
