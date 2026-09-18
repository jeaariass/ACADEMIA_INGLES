from __future__ import annotations

import os
import tempfile
import time
import uuid
import zipfile
from functools import wraps
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import db
from .question_bulk_import import (
    QuestionImportError,
    apply_question_only_import,
    build_question_only_template,
    validate_question_only_import,
)

question_import_bp = Blueprint("question_import", __name__, url_prefix="/admin/question-import")

IMPORT_DIR = Path(tempfile.gettempdir()) / "english_practice_hub_question_imports"
MAX_BYTES = 10 * 1024 * 1024
MAX_AGE_SECONDS = 24 * 60 * 60


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Administrator access only.", "warning")
            return redirect(url_for("main.dashboard"))
        return func(*args, **kwargs)

    return wrapper


def _cleanup_import_files():
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - MAX_AGE_SECONDS
    for path in IMPORT_DIR.glob("*.xlsx"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def _import_path(token):
    if not token or len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return None
    return IMPORT_DIR / f"{token}.xlsx"


def _clear_session():
    session.pop("question_import_token", None)
    session.pop("question_import_filename", None)


def _is_valid_xlsx_container(path):
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


@question_import_bp.route("/")
@login_required
@admin_required
def index():
    _cleanup_import_files()
    return render_template("admin_question_import.html", preview=None, upload_filename=None, token=None)


@question_import_bp.route("/template")
@login_required
@admin_required
def template():
    return send_file(
        build_question_only_template(),
        as_attachment=True,
        download_name="plantilla_preguntas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@question_import_bp.route("/preview", methods=["POST"])
@login_required
@admin_required
def preview():
    _cleanup_import_files()
    upload = request.files.get("file")

    if upload is None or not upload.filename:
        flash("Select an Excel file before validating.", "warning")
        return redirect(url_for("question_import.index"))

    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".xlsx"):
        flash("This importer accepts .xlsx files only. Download and use the provided template.", "danger")
        return redirect(url_for("question_import.index"))

    if request.content_length and request.content_length > MAX_BYTES:
        flash("The uploaded file is larger than the 10 MB limit.", "danger")
        return redirect(url_for("question_import.index"))

    token = uuid.uuid4().hex
    path = _import_path(token)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    try:
        if path.stat().st_size > MAX_BYTES:
            path.unlink(missing_ok=True)
            flash("The uploaded file is larger than the 10 MB limit.", "danger")
            return redirect(url_for("question_import.index"))
        if not _is_valid_xlsx_container(path):
            path.unlink(missing_ok=True)
            flash("The uploaded file is not a valid XLSX workbook.", "danger")
            return redirect(url_for("question_import.index"))

        preview = validate_question_only_import(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        _clear_session()
        flash(f"The workbook could not be validated: {exc}", "danger")
        return redirect(url_for("question_import.index"))

    if preview["errors"]:
        path.unlink(missing_ok=True)
        _clear_session()
        return render_template(
            "admin_question_import.html",
            preview=preview,
            upload_filename=filename,
            token=None,
        )

    session["question_import_token"] = token
    session["question_import_filename"] = filename
    return render_template(
        "admin_question_import.html",
        preview=preview,
        upload_filename=filename,
        token=token,
    )


@question_import_bp.route("/confirm", methods=["POST"])
@login_required
@admin_required
def confirm():
    token = (request.form.get("token") or "").strip().lower()
    expected_token = session.get("question_import_token")

    if not token or token != expected_token:
        _clear_session()
        flash("The import preview expired or does not match this session. Validate the file again.", "warning")
        return redirect(url_for("question_import.index"))

    path = _import_path(token)
    if path is None or not path.exists():
        _clear_session()
        flash("The temporary upload is no longer available. Validate the file again.", "warning")
        return redirect(url_for("question_import.index"))

    try:
        result = apply_question_only_import(path)
    except QuestionImportError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("question_import.index"))
    except Exception as exc:
        db.session.rollback()
        flash(f"Import failed and no partial changes were committed: {exc}", "danger")
        return redirect(url_for("question_import.index"))
    finally:
        path.unlink(missing_ok=True)
        _clear_session()

    flash(
        (
            "Question import completed: "
            f"{result['created_questions']} questions created, "
            f"{result['updated_questions']} questions updated."
        ),
        "success",
    )
    return redirect(url_for("question_import.index"))
