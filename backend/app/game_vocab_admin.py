from __future__ import annotations

import tempfile
import time
import uuid
import zipfile
from functools import wraps
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from . import db
from .game_vocab_bulk import (
    GameVocabularyImportError,
    apply_game_vocabulary_import,
    build_game_vocabulary_export,
    build_game_vocabulary_template,
    validate_game_vocabulary_import,
)
from .game_vocabulary import ARCADE_GAMES, KIDS_GAMES, LEVEL_ORDER, normalize_bool, normalize_code, normalize_games
from .models import GameVocabulary, GameVocabularyCategory, KidsWordProgress

bp = Blueprint("game_vocab_admin", __name__, url_prefix="/admin/game-vocabulary")
IMPORT_DIR = Path(tempfile.gettempdir()) / "english_practice_game_vocab"
MAX_BYTES = 10 * 1024 * 1024


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Administrator access only.", "warning")
            return redirect(url_for("main.dashboard"))
        return fn(*args, **kwargs)
    return wrapped


def _truth(name, default=True):
    return normalize_bool(request.form.get(name), default)


def _int(name, default, minimum, maximum):
    try: value=int(request.form.get(name, default))
    except (TypeError,ValueError): value=default
    return max(minimum,min(maximum,value))


def _valid_xlsx(path):
    try:
        if not zipfile.is_zipfile(path): return False
        with zipfile.ZipFile(path) as z:
            names={x.filename for x in z.infolist()}
            return "[Content_Types].xml" in names and "xl/workbook.xml" in names and len(names)<5000
    except Exception: return False


def _token_path(token):
    if not token or len(token)!=32 or any(c not in "0123456789abcdef" for c in token): return None
    return IMPORT_DIR/f"{token}.xlsx"


@bp.get("/")
@login_required
@admin_required
def index():
    category=(request.args.get("category") or "ALL").strip().lower()
    audience=(request.args.get("audience") or "ALL").strip().lower()
    q=(request.args.get("q") or "").strip()
    query=GameVocabulary.query.join(GameVocabularyCategory)
    if category!="all": query=query.filter(GameVocabularyCategory.code==category)
    if audience=="kids": query=query.filter(GameVocabulary.kids_enabled.is_(True))
    elif audience=="standard": query=query.filter(GameVocabulary.standard_enabled.is_(True))
    if q:
        like=f"%{q}%"; query=query.filter(or_(GameVocabulary.key.ilike(like),GameVocabulary.english.ilike(like),GameVocabulary.spanish.ilike(like)))
    words=query.order_by(GameVocabularyCategory.sort_order,GameVocabulary.sort_order,GameVocabulary.english).limit(500).all()
    categories=GameVocabularyCategory.query.order_by(GameVocabularyCategory.sort_order,GameVocabularyCategory.name).all()
    progress_counts=dict(db.session.query(KidsWordProgress.word_key,db.func.sum(KidsWordProgress.exposures)).group_by(KidsWordProgress.word_key).all())
    return render_template("admin_game_vocabulary.html",words=words,categories=categories,progress_counts=progress_counts,kids_games=sorted(KIDS_GAMES),arcade_games=sorted(ARCADE_GAMES),levels=LEVEL_ORDER,filters={"category":category,"audience":audience,"q":q})


@bp.post("/category")
@login_required
@admin_required
def create_category():
    code=normalize_code(request.form.get("code"),60); name=(request.form.get("name") or "").strip()
    if not code or not name:
        flash("Category code and name are required.","danger"); return redirect(url_for("game_vocab_admin.index"))
    if GameVocabularyCategory.query.filter_by(code=code).first():
        flash(f"Category '{code}' already exists.","warning"); return redirect(url_for("game_vocab_admin.index"))
    row=GameVocabularyCategory(code=code,name=name[:120],visual=(request.form.get("visual") or "🎮").strip()[:40],sort_order=_int("sort_order",0,-9999,9999),kids_enabled="kids_enabled" in request.form,standard_enabled="standard_enabled" in request.form,is_active="is_active" in request.form)
    db.session.add(row); db.session.commit(); flash(f"Category '{name}' created.","success"); return redirect(url_for("game_vocab_admin.index"))


@bp.route("/category/<int:category_id>/edit",methods=["GET","POST"])
@login_required
@admin_required
def edit_category(category_id):
    row=GameVocabularyCategory.query.get_or_404(category_id)
    if request.method=="POST":
        code=normalize_code(request.form.get("code"),60); name=(request.form.get("name") or "").strip()
        duplicate=GameVocabularyCategory.query.filter(GameVocabularyCategory.code==code,GameVocabularyCategory.id!=row.id).first()
        if not code or not name or duplicate:
            flash("Use a unique category code and a name.","danger"); return redirect(url_for("game_vocab_admin.edit_category",category_id=row.id))
        row.code=code; row.name=name[:120]; row.visual=(request.form.get("visual") or "🎮").strip()[:40]; row.sort_order=_int("sort_order",0,-9999,9999); row.kids_enabled="kids_enabled" in request.form; row.standard_enabled="standard_enabled" in request.form; row.is_active="is_active" in request.form
        db.session.commit(); flash("Category updated.","success"); return redirect(url_for("game_vocab_admin.index"))
    return render_template("admin_game_category_edit.html",category=row)


@bp.post("/word")
@login_required
@admin_required
def create_word():
    key=normalize_code(request.form.get("key"),80); english=(request.form.get("english") or "").strip(); spanish=(request.form.get("spanish") or "").strip()
    try: category_id=int(request.form.get("category_id"))
    except (TypeError,ValueError): category_id=0
    if not key or not english or not spanish or GameVocabulary.query.filter_by(key=key).first() or not GameVocabularyCategory.query.get(category_id):
        flash("Use a unique key, English/Spanish values, and a valid category.","danger"); return redirect(url_for("game_vocab_admin.index"))
    row=GameVocabulary(key=key,category_id=category_id,english=english[:160],spanish=spanish[:160],visual=(request.form.get("visual") or "✨").strip()[:80],kids_difficulty=_int("kids_difficulty",1,1,3),cefr_level=(request.form.get("cefr_level") or "A1").upper(),standard_difficulty=_int("standard_difficulty",1,1,5),kids_enabled="kids_enabled" in request.form,standard_enabled="standard_enabled" in request.form,kids_games=request.form.getlist("kids_games"),arcade_games=request.form.getlist("arcade_games"),sort_order=_int("sort_order",0,-9999,9999),is_active="is_active" in request.form)
    if row.cefr_level not in LEVEL_ORDER: row.cefr_level="A1"
    row.kids_games=[x for x in row.kids_games if x in KIDS_GAMES]; row.arcade_games=[x for x in row.arcade_games if x in ARCADE_GAMES]
    db.session.add(row); db.session.commit(); flash(f"'{english}' added to the game vocabulary.","success"); return redirect(url_for("game_vocab_admin.index"))


@bp.route("/word/<int:word_id>/edit",methods=["GET","POST"])
@login_required
@admin_required
def edit_word(word_id):
    row=GameVocabulary.query.get_or_404(word_id); categories=GameVocabularyCategory.query.order_by(GameVocabularyCategory.sort_order,GameVocabularyCategory.name).all()
    if request.method=="POST":
        key=normalize_code(request.form.get("key"),80); english=(request.form.get("english") or "").strip(); spanish=(request.form.get("spanish") or "").strip()
        duplicate=GameVocabulary.query.filter(GameVocabulary.key==key,GameVocabulary.id!=row.id).first()
        try: category_id=int(request.form.get("category_id"))
        except (TypeError,ValueError): category_id=0
        if not key or not english or not spanish or duplicate or not GameVocabularyCategory.query.get(category_id):
            flash("Use a unique key, English/Spanish values, and a valid category.","danger"); return redirect(url_for("game_vocab_admin.edit_word",word_id=row.id))
        row.key=key; row.english=english[:160]; row.spanish=spanish[:160]; row.visual=(request.form.get("visual") or "✨").strip()[:80]; row.category_id=category_id; row.kids_difficulty=_int("kids_difficulty",1,1,3); row.cefr_level=(request.form.get("cefr_level") or "A1").upper(); row.standard_difficulty=_int("standard_difficulty",1,1,5); row.kids_enabled="kids_enabled" in request.form; row.standard_enabled="standard_enabled" in request.form; row.kids_games=[x for x in request.form.getlist("kids_games") if x in KIDS_GAMES]; row.arcade_games=[x for x in request.form.getlist("arcade_games") if x in ARCADE_GAMES]; row.sort_order=_int("sort_order",0,-9999,9999); row.is_active="is_active" in request.form
        if row.cefr_level not in LEVEL_ORDER: row.cefr_level="A1"
        db.session.commit(); flash("Game vocabulary updated.","success"); return redirect(url_for("game_vocab_admin.index"))
    exposures=db.session.query(db.func.sum(KidsWordProgress.exposures)).filter(KidsWordProgress.word_key==row.key).scalar() or 0
    return render_template("admin_game_word_edit.html",word=row,categories=categories,kids_games=sorted(KIDS_GAMES),arcade_games=sorted(ARCADE_GAMES),levels=LEVEL_ORDER,exposures=exposures)


@bp.get("/template.xlsx")
@login_required
@admin_required
def template():
    return send_file(build_game_vocabulary_template(),as_attachment=True,download_name="game_vocabulary_template.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/export.xlsx")
@login_required
@admin_required
def export():
    return send_file(build_game_vocabulary_export(),as_attachment=True,download_name="game_vocabulary_current.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/import",methods=["GET","POST"])
@login_required
@admin_required
def import_excel():
    preview=None
    if request.method=="POST":
        upload=request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose an .xlsx file.","danger"); return redirect(url_for("game_vocab_admin.import_excel"))
        upload.seek(0,2); size=upload.tell(); upload.seek(0)
        if size>MAX_BYTES or not upload.filename.lower().endswith(".xlsx"):
            flash("Use an .xlsx file up to 10 MB.","danger"); return redirect(url_for("game_vocab_admin.import_excel"))
        IMPORT_DIR.mkdir(parents=True,exist_ok=True); token=uuid.uuid4().hex; path=_token_path(token); upload.save(path)
        if not _valid_xlsx(path): path.unlink(missing_ok=True); flash("The uploaded file is not a valid XLSX workbook.","danger"); return redirect(url_for("game_vocab_admin.import_excel"))
        preview=validate_game_vocabulary_import(path); session["game_vocab_import_token"]=token
    return render_template("admin_game_vocabulary_import.html",preview=preview)


@bp.post("/import/confirm")
@login_required
@admin_required
def confirm_import():
    path=_token_path(session.get("game_vocab_import_token"))
    if not path or not path.exists():
        flash("Import preview expired. Upload the workbook again.","warning"); return redirect(url_for("game_vocab_admin.import_excel"))
    try:
        result=apply_game_vocabulary_import(path)
        flash(f"Import complete: {result['created_categories']} categories created, {result['updated_categories']} updated; {result['created_words']} words created, {result['updated_words']} updated.","success")
    except GameVocabularyImportError as exc:
        flash(str(exc),"danger"); return redirect(url_for("game_vocab_admin.import_excel"))
    finally:
        path.unlink(missing_ok=True); session.pop("game_vocab_import_token",None)
    return redirect(url_for("game_vocab_admin.index"))
