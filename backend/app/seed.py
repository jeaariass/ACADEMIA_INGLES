import json
import os
from pathlib import Path

from . import db
from .models import LibraryItem, SpeakingExercise, User, WritingPrompt
from .security import password_policy_error
from .game_vocabulary import seed_game_vocabulary


BASE_DIR = Path(__file__).resolve().parents[1]
LIBRARY_SEED_PATH = BASE_DIR / "content" / "library" / "starter_library.json"


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_production():
    return (os.getenv("APP_ENV") or "development").strip().lower() == "production"


def ensure_user(username, full_name, role, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
    return user


def seed_library_items():
    if not LIBRARY_SEED_PATH.exists():
        return 0

    data = json.loads(LIBRARY_SEED_PATH.read_text(encoding="utf-8"))
    count = 0
    for raw in data:
        code = raw["code"].strip().upper()
        # Starter content is create-only. Administrator edits/imports survive restarts.
        item = LibraryItem.query.filter_by(code=code).first()
        if item:
            continue

        content = raw["content_text"].strip()
        item = LibraryItem(
            code=code,
            level_code=raw.get("level_code", "A1").strip().upper(),
            category=raw.get("category", "story").strip().lower(),
            title=raw["title"].strip(),
            summary=raw.get("summary", "").strip(),
            content_text=content,
            source_label=raw.get("source_label") or "English Practice Hub original",
            source_url=raw.get("source_url"),
            word_count=len(content.split()),
            sort_order=int(raw.get("sort_order", 0)),
            is_published=bool(raw.get("is_published", True)),
        )
        db.session.add(item)
        count += 1
    return count



def seed_speaking_exercises():
    path = Path(__file__).resolve().parents[1] / "content" / "speaking" / "starter_speaking.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if SpeakingExercise.query.filter_by(code=row["code"]).first():
            continue
        db.session.add(SpeakingExercise(
            code=row["code"],
            level_code=row.get("level", "A1"),
            activity_type=row.get("type", "repeat"),
            title=row["title"],
            prompt=row["prompt"],
            instructions=row.get("instructions", ""),
            expected_text=row.get("expected_text"),
            target_vocabulary=row.get("target_vocabulary", []),
            sort_order=int(row.get("order", 0)),
            is_published=True,
        ))



def seed_writing_prompts():
    path = Path(__file__).resolve().parents[1] / "content" / "writing" / "starter_writing.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if WritingPrompt.query.filter_by(code=row["code"]).first():
            continue
        db.session.add(WritingPrompt(
            code=row["code"], level_code=row.get("level", "A1"), title=row["title"],
            prompt=row["prompt"], instructions=row.get("instructions", ""),
            min_words=int(row.get("min_words", 30)), max_words=int(row.get("max_words", 80)),
            target_vocabulary=row.get("target_vocabulary", []), target_connectors=row.get("target_connectors", []),
            sort_order=int(row.get("order", 0)), is_published=True,
        ))


def seed_initial_data():
    """Create the first administrator, optional demo students and starter library."""
    production = _is_production()
    admin_username = (os.getenv("ADMIN_USERNAME") or ("" if production else "admin")).strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ("" if production else "Admin123*")

    if not admin_username or not admin_password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD are required for initial production setup.")
    if production:
        policy_error = password_policy_error(admin_password)
        if policy_error:
            raise RuntimeError(f"ADMIN_PASSWORD is not production-ready: {policy_error}")

    ensure_user(admin_username, "Administrator", "admin", admin_password)

    seed_demo = _env_bool("SEED_DEMO_USERS", default=not production)
    if seed_demo:
        ensure_user(
            os.getenv("STUDENT1_USERNAME", "student1"),
            "Student 1",
            "student",
            os.getenv("STUDENT1_PASSWORD", "Student123*"),
        )
        ensure_user(
            os.getenv("STUDENT2_USERNAME", "student2"),
            "Student 2",
            "student",
            os.getenv("STUDENT2_PASSWORD", "Student123*"),
        )

    seed_library_items()
    seed_speaking_exercises()
    seed_writing_prompts()
    seed_game_vocabulary()
    db.session.commit()
