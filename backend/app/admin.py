from functools import wraps
import json
from pathlib import Path
import csv
import io
import tempfile
import time
import uuid
import os
import zipfile

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
    Response,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from . import db
from .admin_analytics import build_admin_analytics, build_question_analysis
from .bulk_import import (
    BulkImportError,
    apply_bulk_import,
    build_difficulty_review_workbook,
    build_excel_template,
    validate_bulk_import,
)
from .library_bulk_import import (
    CATEGORY_LABELS as LIBRARY_CATEGORY_LABELS,
    LibraryBulkImportError,
    apply_library_import,
    build_library_export,
    build_library_template,
    validate_library_import,
)
from .security import password_policy_error
from .models import (
    AssessmentAttempt,
    Attempt,
    ArcadeRun,
    GameRun,
    KidsGameRun,
    KidsWordProgress,
    Level,
    LibraryItem,
    Question,
    SavedVocabulary,
    SpeakingAttempt,
    Topic,
    TopicProgress,
    User,
    UserTopicPlan,
    WritingSubmission,
)

admin_bp = Blueprint("admin", __name__)

BULK_IMPORT_DIR = Path(tempfile.gettempdir()) / "english_practice_hub_imports"
BULK_IMPORT_MAX_BYTES = 10 * 1024 * 1024
BULK_IMPORT_MAX_AGE_SECONDS = 24 * 60 * 60
LIBRARY_IMPORT_DIR = Path(tempfile.gettempdir()) / "english_practice_hub_library_imports"

VALID_SKILLS = {"grammar", "vocabulary", "reading", "listening"}
VALID_QUESTION_TYPES = {
    "multiple_choice",
    "reading_multiple_choice",
    "listening_multiple_choice",
    "error_identification",
    "reading_comprehension",
    "listening_comprehension",
}


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Administrator access only.", "warning")
            return redirect(url_for("main.dashboard"))
        return func(*args, **kwargs)

    return wrapper


def _normalize_username(value):
    return (value or "").strip()


def _validate_role(value):
    role = (value or "student").strip().lower()
    return role if role in {"student", "admin"} else None


def _validate_learning_mode(value):
    mode = (value or "standard").strip().lower()
    return mode if mode in {"standard", "kids"} else None


def _cleanup_bulk_import_files():
    BULK_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - BULK_IMPORT_MAX_AGE_SECONDS
    for path in BULK_IMPORT_DIR.glob("*.xlsx"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def _bulk_import_path(token):
    if not token or len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return None
    return BULK_IMPORT_DIR / f"{token}.xlsx"


def _clear_bulk_import_session():
    session.pop("bulk_import_token", None)
    session.pop("bulk_import_filename", None)


def _cleanup_library_import_files():
    LIBRARY_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - BULK_IMPORT_MAX_AGE_SECONDS
    for path in LIBRARY_IMPORT_DIR.glob("*.xlsx"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def _library_import_path(token):
    if not token or len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return None
    return LIBRARY_IMPORT_DIR / f"{token}.xlsx"


def _clear_library_import_session():
    session.pop("library_import_token", None)
    session.pop("library_import_filename", None)


def _is_valid_xlsx_container(path):
    """Reject renamed/non-XLSX uploads before openpyxl processes them."""
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            if len(entries) > 5000:
                return False
            if sum(item.file_size for item in entries) > 50 * 1024 * 1024:
                return False
            names = {item.filename for item in entries}
            return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except (OSError, zipfile.BadZipFile):
        return False


def _list_field(value):
    raw = (value or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.replace("\r", "").replace("|", "\n").split("\n") if item.strip()]


def _mistakes_field(value):
    raw = (value or "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("Common mistakes must be a JSON list.")
    clean = []
    for item in parsed:
        if not isinstance(item, dict) or not (item.get("wrong") and item.get("correct")):
            raise ValueError("Each common mistake requires 'wrong' and 'correct'.")
        clean.append({"wrong": str(item["wrong"]).strip(), "correct": str(item["correct"]).strip()})
    return clean


def _unique_code(model, code, current_id=None):
    query = model.query.filter(func.lower(model.code) == code.lower())
    if current_id is not None:
        query = query.filter(model.id != current_id)
    return query.first()


@admin_bp.route("/")
@login_required
@admin_required
def panel():
    users = User.query.order_by(User.role.desc(), User.full_name.asc(), User.username.asc()).all()
    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    attempts = Attempt.query.order_by(Attempt.created_at.desc()).limit(20).all()

    user_stats = {}
    for user in users:
        user_stats[user.id] = {
            "practice_attempts": Attempt.query.filter_by(user_id=user.id).count(),
            "assessment_attempts": AssessmentAttempt.query.filter_by(user_id=user.id).count(),
            "completed_lessons": TopicProgress.query.filter_by(
                user_id=user.id,
                completed=True,
            ).count(),
        }

    return render_template(
        "admin.html",
        users=users,
        levels=levels,
        attempts=attempts,
        user_stats=user_stats,
    )


@admin_bp.route("/analytics")
@login_required
@admin_required
def analytics():
    dashboard = build_admin_analytics()

    level = (request.args.get("level") or "ALL").strip().upper()
    skill = (request.args.get("skill") or "ALL").strip().lower()
    item_status = (request.args.get("status") or "ALL").strip().lower()
    try:
        min_responses = max(0, int(request.args.get("min_responses", 0)))
    except (TypeError, ValueError):
        min_responses = 0

    question_rows, _ = build_question_analysis(
        level_code=level,
        skill=skill,
        status=item_status,
        min_responses=min_responses,
    )

    return render_template(
        "admin_analytics.html",
        dashboard=dashboard,
        question_rows=question_rows[:250],
        question_total_filtered=len(question_rows),
        filters={
            "level": level,
            "skill": skill,
            "status": item_status,
            "min_responses": min_responses,
        },
    )


@admin_bp.route("/analytics/questions.csv")
@login_required
@admin_required
def analytics_questions_csv():
    level = (request.args.get("level") or "ALL").strip().upper()
    skill = (request.args.get("skill") or "ALL").strip().lower()
    item_status = (request.args.get("status") or "ALL").strip().lower()
    try:
        min_responses = max(0, int(request.args.get("min_responses", 0)))
    except (TypeError, ValueError):
        min_responses = 0

    rows, _ = build_question_analysis(
        level_code=level,
        skill=skill,
        status=item_status,
        min_responses=min_responses,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "code", "level", "topic_code", "topic", "skill", "question_type",
        "level_difficulty", "academic_responses", "academic_correct",
        "academic_accuracy_pct", "avg_formal_response_seconds",
        "game_responses", "game_accuracy_pct", "status", "prompt",
    ])
    for row in rows:
        writer.writerow([
            row["code"], row["level"], row["topic_code"] or "", row["topic"],
            row["skill"], row["question_type"], row["level_difficulty"],
            row["academic_responses"], row["academic_correct"],
            "" if row["academic_rate"] is None else row["academic_rate"],
            "" if row["avg_response_seconds"] is None else row["avg_response_seconds"],
            row["game_responses"],
            "" if row["game_rate"] is None else row["game_rate"],
            row["status"], row["prompt"],
        ])

    csv_text = "\ufeff" + output.getvalue()
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=question_item_analysis.csv"
        },
    )



@admin_bp.route("/content")
@login_required
@admin_required
def content_manager():
    kind = (request.args.get("kind") or "questions").strip().lower()
    if kind not in {"topics", "questions", "readings"}:
        kind = "questions"
    level = (request.args.get("level") or "ALL").strip().upper()
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "ALL").strip().lower()

    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    rows = []
    if kind == "topics":
        query = Topic.query.join(Level, Topic.level_id == Level.id)
        if level != "ALL":
            query = query.filter(Level.code == level)
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(
                or_(Topic.code.ilike(pattern), Topic.title.ilike(pattern), Topic.objective.ilike(pattern))
            )
        rows = query.order_by(Level.sort_order.asc(), Topic.sort_order.asc(), Topic.id.asc()).limit(250).all()
    elif kind == "readings":
        query = LibraryItem.query
        if level != "ALL":
            query = query.filter(LibraryItem.level_code == level)
        if category != "ALL":
            query = query.filter(LibraryItem.category == category)
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(
                or_(
                    LibraryItem.code.ilike(pattern),
                    LibraryItem.title.ilike(pattern),
                    LibraryItem.summary.ilike(pattern),
                )
            )
        rows = query.order_by(LibraryItem.level_code.asc(), LibraryItem.sort_order.asc(), LibraryItem.id.asc()).limit(250).all()
    else:
        query = Question.query.join(Topic, Question.topic_id == Topic.id).join(Level, Topic.level_id == Level.id)
        if level != "ALL":
            query = query.filter(Level.code == level)
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(
                or_(Question.code.ilike(pattern), Question.prompt.ilike(pattern), Topic.title.ilike(pattern))
            )
        rows = query.order_by(Level.sort_order.asc(), Topic.sort_order.asc(), Question.sort_order.asc(), Question.id.asc()).limit(250).all()

    counts = {
        "topics": Topic.query.count(),
        "questions": Question.query.count(),
        "readings": LibraryItem.query.count(),
    }
    return render_template(
        "admin_content.html",
        kind=kind,
        rows=rows,
        levels=levels,
        selected_level=level,
        selected_category=category,
        query_text=query_text,
        categories=LIBRARY_CATEGORY_LABELS,
        counts=counts,
    )


@admin_bp.route("/content/topic/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        title = (request.form.get("title") or "").strip()
        theory = (request.form.get("theory") or "").strip()
        if not code or not title or not theory:
            flash("Code, title and theory are required.", "danger")
            return redirect(url_for("admin.edit_topic", topic_id=topic.id))
        if _unique_code(Topic, code, topic.id):
            flash(f"Topic code '{code}' is already in use.", "danger")
            return redirect(url_for("admin.edit_topic", topic_id=topic.id))
        try:
            mistakes = _mistakes_field(request.form.get("common_mistakes"))
            sort_order = int(request.form.get("sort_order") or 0)
            level_id = int(request.form.get("level_id"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            flash(f"Could not save topic: {exc}", "danger")
            return redirect(url_for("admin.edit_topic", topic_id=topic.id))
        if not Level.query.get(level_id):
            flash("Selected level does not exist.", "danger")
            return redirect(url_for("admin.edit_topic", topic_id=topic.id))

        topic.code = code
        topic.level_id = level_id
        topic.sort_order = sort_order
        topic.title = title
        topic.objective = (request.form.get("objective") or "").strip()
        topic.theory = theory
        topic.examples = _list_field(request.form.get("examples"))
        topic.common_mistakes = mistakes
        topic.key_vocabulary = _list_field(request.form.get("key_vocabulary"))
        topic.youtube_video_id = (request.form.get("youtube_video_id") or "").strip() or None
        topic.is_published = request.form.get("is_published") == "1"
        db.session.commit()
        flash(f"Topic '{topic.code}' updated.", "success")
        return redirect(url_for("admin.content_manager", kind="topics", level=topic.level.code))

    return render_template(
        "admin_topic_edit.html",
        topic=topic,
        levels=levels,
        examples_text="\n".join(topic.examples or []),
        vocabulary_text="\n".join(topic.key_vocabulary or []),
        mistakes_text=json.dumps(topic.common_mistakes or [], ensure_ascii=False, indent=2),
    )


@admin_bp.route("/content/question/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    topics = (
        Topic.query.join(Level, Topic.level_id == Level.id)
        .order_by(Level.sort_order.asc(), Topic.sort_order.asc(), Topic.id.asc())
        .all()
    )
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        prompt = (request.form.get("prompt") or "").strip()
        correct = (request.form.get("correct_option") or "").strip().upper()
        skill = (request.form.get("skill") or "").strip().lower()
        question_type = (request.form.get("question_type") or "").strip().lower()
        options = [(request.form.get(f"option_{x}") or "").strip() for x in "abcd"]
        if not code or not prompt or not all(options):
            flash("Code, prompt and all four options are required.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if _unique_code(Question, code, question.id):
            flash(f"Question code '{code}' is already in use.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if correct not in {"A", "B", "C", "D"}:
            flash("Correct option must be A, B, C or D.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if skill not in VALID_SKILLS or question_type not in VALID_QUESTION_TYPES:
            flash("Invalid skill or question type.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        try:
            sort_order = int(request.form.get("sort_order") or 0)
            difficulty = max(1, min(5, int(request.form.get("difficulty") or 1)))
            level_difficulty = max(1, min(5, int(request.form.get("level_difficulty") or 3)))
            max_audio_plays = max(1, int(request.form.get("max_audio_plays") or 2))
            audio_rate = float(request.form.get("audio_rate") or 1.0)
            topic_id = int(request.form.get("topic_id"))
        except (TypeError, ValueError):
            flash("Order, difficulty and audio fields must contain valid numbers.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        target_topic = Topic.query.get(topic_id)
        if not target_topic:
            flash("Selected topic does not exist.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if question.passage_id is not None and topic_id != question.topic_id:
            flash("A passage-linked question cannot be moved to another topic from this editor.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        audio_text = (request.form.get("audio_text") or "").strip() or None
        if question_type == "listening_multiple_choice" and not audio_text:
            flash("Standalone listening multiple choice requires audio text.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if question_type in {"reading_comprehension", "listening_comprehension"} and question.passage_id is None:
            flash("Comprehension question types require an existing passage relationship.", "danger")
            return redirect(url_for("admin.edit_question", question_id=question.id))
        if question.passage_id is not None:
            expected = "reading_comprehension" if question.passage.passage_type == "reading" else "listening_comprehension"
            if question_type in {"reading_comprehension", "listening_comprehension"} and question_type != expected:
                flash(f"This passage requires question type '{expected}'.", "danger")
                return redirect(url_for("admin.edit_question", question_id=question.id))

        question.code = code
        question.topic_id = topic_id
        question.sort_order = sort_order
        question.skill = skill
        question.question_type = question_type
        question.difficulty = difficulty
        question.level_difficulty = level_difficulty
        question.prompt = prompt
        question.option_a, question.option_b, question.option_c, question.option_d = options
        question.correct_option = correct
        question.explanation = (request.form.get("explanation") or "").strip()
        question.audio_text = audio_text
        question.audio_accent = (request.form.get("audio_accent") or "en-US").strip() or "en-US"
        question.audio_rate = max(0.5, min(1.5, audio_rate))
        question.max_audio_plays = max_audio_plays
        question.is_active = request.form.get("is_active") == "1"
        db.session.commit()
        flash(f"Question '{question.code}' updated.", "success")
        return redirect(url_for("admin.content_manager", kind="questions", level=question.topic.level.code))

    return render_template(
        "admin_question_edit.html",
        question=question,
        topics=topics,
        skills=sorted(VALID_SKILLS),
        question_types=sorted(VALID_QUESTION_TYPES),
    )


@admin_bp.route("/content/reading/new", methods=["GET", "POST"])
@admin_bp.route("/content/reading/<int:reading_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_reading(reading_id=None):
    reading = LibraryItem.query.get_or_404(reading_id) if reading_id is not None else None
    levels = Level.query.order_by(Level.sort_order.asc(), Level.code.asc()).all()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        level_code = (request.form.get("level_code") or "").strip().upper()
        category = (request.form.get("category") or "").strip().lower()
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content_text") or "").strip()
        if not code or not title or not content:
            flash("Code, title and content are required.", "danger")
            return redirect(request.url)
        current_id = reading.id if reading else None
        if _unique_code(LibraryItem, code, current_id):
            flash(f"Reading code '{code}' is already in use.", "danger")
            return redirect(request.url)
        if not Level.query.filter_by(code=level_code).first():
            flash("Selected CEFR level does not exist.", "danger")
            return redirect(request.url)
        if category not in LIBRARY_CATEGORY_LABELS:
            flash("Invalid library category.", "danger")
            return redirect(request.url)
        try:
            sort_order = int(request.form.get("sort_order") or 0)
        except ValueError:
            flash("Order must be a whole number.", "danger")
            return redirect(request.url)
        source_url = (request.form.get("source_url") or "").strip() or None
        if source_url and not source_url.lower().startswith(("http://", "https://")):
            flash("Source URL must start with http:// or https://.", "danger")
            return redirect(request.url)

        if reading is None:
            reading = LibraryItem(code=code, title=title, content_text=content)
            db.session.add(reading)
        reading.code = code
        reading.level_code = level_code
        reading.category = category
        reading.sort_order = sort_order
        reading.title = title
        reading.summary = (request.form.get("summary") or "").strip()
        reading.content_text = content
        reading.source_label = (request.form.get("source_label") or "").strip() or None
        reading.source_url = source_url
        reading.word_count = len(content.split())
        reading.is_published = request.form.get("is_published") == "1"
        db.session.commit()
        flash(f"Reading '{reading.code}' saved.", "success")
        return redirect(url_for("admin.content_manager", kind="readings", level=reading.level_code))

    return render_template(
        "admin_library_edit.html",
        reading=reading,
        levels=levels,
        categories=LIBRARY_CATEGORY_LABELS,
    )


@admin_bp.route("/level", methods=["POST"])
@login_required
@admin_required
def create_level():
    code = request.form["code"].strip().upper()
    name = request.form["name"].strip()
    description = request.form.get("description", "").strip()

    if Level.query.filter_by(code=code).first():
        flash(f"Level '{code}' already exists.", "warning")
        return redirect(url_for("admin.panel"))

    db.session.add(Level(code=code, name=name, description=description))
    db.session.commit()
    flash(f"Level '{code}' created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/topic", methods=["POST"])
@login_required
@admin_required
def create_topic():
    db.session.add(
        Topic(
            level_id=int(request.form["level_id"]),
            title=request.form["title"].strip(),
            theory=request.form["theory"].strip(),
        )
    )
    db.session.commit()
    flash("Topic created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/question", methods=["POST"])
@login_required
@admin_required
def create_question():
    db.session.add(
        Question(
            topic_id=int(request.form["topic_id"]),
            prompt=request.form["prompt"].strip(),
            option_a=request.form["option_a"].strip(),
            option_b=request.form["option_b"].strip(),
            option_c=request.form["option_c"].strip(),
            option_d=request.form["option_d"].strip(),
            correct_option=request.form["correct_option"].strip().upper(),
            explanation=request.form.get("explanation", "").strip(),
            level_difficulty=max(1, min(5, int(request.form.get("level_difficulty", 3)))),
        )
    )
    db.session.commit()
    flash("Question created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/bulk-import")
@login_required
@admin_required
def bulk_import():
    _cleanup_bulk_import_files()
    return render_template("admin_bulk_import.html", preview=None, upload_filename=None, token=None)


@admin_bp.route("/bulk-import/template")
@login_required
@admin_required
def bulk_import_template():
    return send_file(
        build_excel_template(),
        as_attachment=True,
        download_name="plantilla_carga_masiva_ingles.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/bulk-import/difficulty-bank")
@login_required
@admin_required
def bulk_import_difficulty_bank():
    return send_file(
        build_difficulty_review_workbook(),
        as_attachment=True,
        download_name="banco_preguntas_revision_dificultad.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/bulk-import/preview", methods=["POST"])
@login_required
@admin_required
def bulk_import_preview():
    _cleanup_bulk_import_files()
    upload = request.files.get("file")

    if upload is None or not upload.filename:
        flash("Select an Excel file before validating.", "warning")
        return redirect(url_for("admin.bulk_import"))

    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".xlsx"):
        flash("Phase 1B accepts .xlsx files only. Download and use the provided template.", "danger")
        return redirect(url_for("admin.bulk_import"))

    if request.content_length and request.content_length > BULK_IMPORT_MAX_BYTES:
        flash("The uploaded file is larger than the 10 MB limit.", "danger")
        return redirect(url_for("admin.bulk_import"))

    token = uuid.uuid4().hex
    path = _bulk_import_path(token)
    BULK_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    try:
        if path.stat().st_size > BULK_IMPORT_MAX_BYTES:
            path.unlink(missing_ok=True)
            flash("The uploaded file is larger than the 10 MB limit.", "danger")
            return redirect(url_for("admin.bulk_import"))
        if not _is_valid_xlsx_container(path):
            path.unlink(missing_ok=True)
            flash("The uploaded file is not a valid XLSX workbook.", "danger")
            return redirect(url_for("admin.bulk_import"))

        preview = validate_bulk_import(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        _clear_bulk_import_session()
        flash(f"The workbook could not be validated: {exc}", "danger")
        return redirect(url_for("admin.bulk_import"))

    if preview["errors"]:
        path.unlink(missing_ok=True)
        _clear_bulk_import_session()
        return render_template(
            "admin_bulk_import.html",
            preview=preview,
            upload_filename=filename,
            token=None,
        )

    session["bulk_import_token"] = token
    session["bulk_import_filename"] = filename
    return render_template(
        "admin_bulk_import.html",
        preview=preview,
        upload_filename=filename,
        token=token,
    )


@admin_bp.route("/bulk-import/confirm", methods=["POST"])
@login_required
@admin_required
def bulk_import_confirm():
    token = (request.form.get("token") or "").strip().lower()
    expected_token = session.get("bulk_import_token")

    if not token or token != expected_token:
        _clear_bulk_import_session()
        flash("The import preview expired or does not match this session. Validate the file again.", "warning")
        return redirect(url_for("admin.bulk_import"))

    path = _bulk_import_path(token)
    if path is None or not path.exists():
        _clear_bulk_import_session()
        flash("The temporary upload is no longer available. Validate the file again.", "warning")
        return redirect(url_for("admin.bulk_import"))

    try:
        result = apply_bulk_import(path)
    except BulkImportError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.bulk_import"))
    except Exception as exc:
        db.session.rollback()
        flash(f"Import failed and no partial changes were committed: {exc}", "danger")
        return redirect(url_for("admin.bulk_import"))
    finally:
        path.unlink(missing_ok=True)
        _clear_bulk_import_session()

    flash(
        (
            "Bulk import completed: "
            f"{result['created_topics']} topics created, "
            f"{result['updated_topics']} topics updated, "
            f"{result['created_questions']} questions created, "
            f"{result['updated_questions']} questions updated."
        ),
        "success",
    )
    return redirect(url_for("admin.bulk_import"))



@admin_bp.route("/library-import")
@login_required
@admin_required
def library_import():
    _cleanup_library_import_files()
    return render_template(
        "admin_library_import.html",
        preview=None,
        upload_filename=None,
        token=None,
    )


@admin_bp.route("/library-import/template")
@login_required
@admin_required
def library_import_template():
    return send_file(
        build_library_template(),
        as_attachment=True,
        download_name="plantilla_carga_masiva_lecturas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/library-import/export")
@login_required
@admin_required
def library_import_export():
    return send_file(
        build_library_export(),
        as_attachment=True,
        download_name="banco_actual_lecturas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/library-import/preview", methods=["POST"])
@login_required
@admin_required
def library_import_preview():
    _cleanup_library_import_files()
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Select an Excel file before validating.", "warning")
        return redirect(url_for("admin.library_import"))
    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".xlsx"):
        flash("Library import accepts .xlsx files only.", "danger")
        return redirect(url_for("admin.library_import"))
    if request.content_length and request.content_length > BULK_IMPORT_MAX_BYTES:
        flash("The uploaded file is larger than the 10 MB limit.", "danger")
        return redirect(url_for("admin.library_import"))

    token = uuid.uuid4().hex
    path = _library_import_path(token)
    LIBRARY_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    try:
        if path.stat().st_size > BULK_IMPORT_MAX_BYTES:
            path.unlink(missing_ok=True)
            flash("The uploaded file is larger than the 10 MB limit.", "danger")
            return redirect(url_for("admin.library_import"))
        if not _is_valid_xlsx_container(path):
            path.unlink(missing_ok=True)
            flash("The uploaded file is not a valid XLSX workbook.", "danger")
            return redirect(url_for("admin.library_import"))
        preview = validate_library_import(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        _clear_library_import_session()
        flash(f"The workbook could not be validated: {exc}", "danger")
        return redirect(url_for("admin.library_import"))

    if preview["errors"]:
        path.unlink(missing_ok=True)
        _clear_library_import_session()
        return render_template(
            "admin_library_import.html",
            preview=preview,
            upload_filename=filename,
            token=None,
        )

    session["library_import_token"] = token
    session["library_import_filename"] = filename
    return render_template(
        "admin_library_import.html",
        preview=preview,
        upload_filename=filename,
        token=token,
    )


@admin_bp.route("/library-import/confirm", methods=["POST"])
@login_required
@admin_required
def library_import_confirm():
    token = (request.form.get("token") or "").strip()
    if token != session.get("library_import_token"):
        flash("The validated library upload is no longer available. Validate the file again.", "warning")
        return redirect(url_for("admin.library_import"))
    path = _library_import_path(token)
    if not path or not path.exists():
        _clear_library_import_session()
        flash("The temporary library upload is no longer available. Validate the file again.", "warning")
        return redirect(url_for("admin.library_import"))

    try:
        result = apply_library_import(path)
    except LibraryBulkImportError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.library_import"))
    except Exception as exc:
        db.session.rollback()
        flash(f"Library import failed and no partial changes were committed: {exc}", "danger")
        return redirect(url_for("admin.library_import"))
    finally:
        path.unlink(missing_ok=True)
        _clear_library_import_session()

    flash(
        f"Library import completed: {result['created_readings']} readings created and "
        f"{result['updated_readings']} updated.",
        "success",
    )
    return redirect(url_for("admin.content_manager", kind="readings"))


@admin_bp.route("/user", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = _normalize_username(request.form.get("username"))
    full_name = (request.form.get("full_name") or "").strip()
    password = request.form.get("password") or ""
    role = _validate_role(request.form.get("role"))
    learning_mode = _validate_learning_mode(request.form.get("learning_mode"))

    if not username:
        flash("Username is required.", "danger")
        return redirect(url_for("admin.panel"))

    if not full_name:
        flash("Full name is required.", "danger")
        return redirect(url_for("admin.panel"))

    if role is None:
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.panel"))
    if learning_mode is None:
        flash("Invalid learning mode.", "danger")
        return redirect(url_for("admin.panel"))
    if role == "admin":
        learning_mode = "standard"

    password_error = password_policy_error(password)
    if password_error:
        flash(password_error, "danger")
        return redirect(url_for("admin.panel"))

    if User.query.filter(func.lower(User.username) == username.lower()).first():
        flash(f"Username '{username}' already exists.", "warning")
        return redirect(url_for("admin.panel"))

    user = User(username=username, full_name=full_name, role=role, learning_mode=learning_mode)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"User '{username}' created.", "success")
    return redirect(url_for("admin.panel"))


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        username = _normalize_username(request.form.get("username"))
        full_name = (request.form.get("full_name") or "").strip()
        role = _validate_role(request.form.get("role"))
        learning_mode = _validate_learning_mode(request.form.get("learning_mode"))
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not username:
            flash("Username is required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if len(username) > 80:
            flash("Username cannot exceed 80 characters.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if not full_name:
            flash("Full name is required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if len(full_name) > 120:
            flash("Full name cannot exceed 120 characters.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if role is None:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))
        if learning_mode is None:
            flash("Invalid learning mode.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))
        if role == "admin":
            learning_mode = "standard"

        duplicate = (
            User.query
            .filter(
                func.lower(User.username) == username.lower(),
                User.id != user.id,
            )
            .first()
        )
        if duplicate:
            flash(f"Username '{username}' is already used by another account.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        # The administrator currently logged in must not accidentally remove
        # their own administrator privileges and lock themselves out.
        if user.id == current_user.id and role != "admin":
            flash("You cannot remove administrator access from your own active account.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if new_password:
            password_error = password_policy_error(new_password)
            if password_error:
                flash(password_error, "danger")
                return redirect(url_for("admin.edit_user", user_id=user.id))
            if new_password != confirm_password:
                flash("The password confirmation does not match.", "danger")
                return redirect(url_for("admin.edit_user", user_id=user.id))

        old_username = user.username

        user.username = username
        user.full_name = full_name
        user.role = role
        user.learning_mode = learning_mode

        if new_password:
            user.set_password(new_password)

        db.session.commit()

        if new_password:
            flash(
                f"User '{username}' updated and password reset successfully.",
                "success",
            )
        elif old_username != username:
            flash(
                f"User '{old_username}' updated. New username: '{username}'.",
                "success",
            )
        else:
            flash(f"User '{username}' updated successfully.", "success")

        return redirect(url_for("admin.panel"))

    stats = {
        "practice_attempts": Attempt.query.filter_by(user_id=user.id).count(),
        "assessment_attempts": AssessmentAttempt.query.filter_by(user_id=user.id).count(),
        "completed_lessons": TopicProgress.query.filter_by(
            user_id=user.id,
            completed=True,
        ).count(),
    }

    return render_template(
        "admin_user_edit.html",
        edited_user=user,
        stats=stats,
    )


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own active account.", "danger")
        return redirect(url_for("admin.panel"))

    history_counts = {
        "practice": Attempt.query.filter_by(user_id=user.id).count(),
        "assessments": AssessmentAttempt.query.filter_by(user_id=user.id).count(),
        "progress": TopicProgress.query.filter_by(user_id=user.id).count(),
        "learning_plan": UserTopicPlan.query.filter_by(user_id=user.id).count(),
        "vocabulary": SavedVocabulary.query.filter_by(user_id=user.id).count(),
        "runner": GameRun.query.filter_by(user_id=user.id).count(),
        "arcade": ArcadeRun.query.filter_by(user_id=user.id).count(),
        "speaking": SpeakingAttempt.query.filter_by(user_id=user.id).count(),
        "writing": WritingSubmission.query.filter_by(user_id=user.id).count(),
        "kids_games": KidsGameRun.query.filter_by(user_id=user.id).count(),
        "kids_words": KidsWordProgress.query.filter_by(user_id=user.id).count(),
    }

    if any(history_counts.values()):
        flash(
            (
                f"User '{user.username}' has learning history and was not deleted. "
                "Edit the account instead so progress and assessment records remain intact."
            ),
            "warning",
        )
        return redirect(url_for("admin.panel"))

    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("admin.panel"))
