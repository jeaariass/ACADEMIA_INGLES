from __future__ import annotations

import re
from collections import Counter

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import db
from .models import WritingPrompt, WritingSubmission

writing_bp = Blueprint("writing", __name__, url_prefix="/writing")
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _words(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", (text or "").lower())


def _metrics(prompt, text):
    words = _words(text)
    unique_ratio = round((len(set(words)) / len(words)) * 100, 1) if words else None
    sentences = [s for s in re.split(r"[.!?]+", text or "") if s.strip()]
    normalized = " ".join(words)
    target_hits = sum(1 for item in prompt.target_vocabulary or [] if " ".join(_words(item)) in normalized)
    connector_hits = sum(1 for item in prompt.target_connectors or [] if " ".join(_words(item)) in normalized)
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "unique_word_ratio": unique_ratio,
        "target_hits": target_hits,
        "connector_hits": connector_hits,
    }


@writing_bp.get("/")
@login_required
def index():
    prompts = WritingPrompt.query.filter_by(is_published=True).order_by(WritingPrompt.sort_order, WritingPrompt.id).all()
    grouped = {code: [] for code in LEVEL_ORDER}
    for prompt in prompts:
        grouped.setdefault(prompt.level_code, []).append(prompt)
    counts = dict(
        db.session.query(WritingSubmission.prompt_id, db.func.count(WritingSubmission.id))
        .filter(WritingSubmission.user_id == current_user.id)
        .group_by(WritingSubmission.prompt_id)
        .all()
    )
    return render_template("writing_index.html", grouped=grouped, counts=counts)


@writing_bp.route("/<int:prompt_id>", methods=["GET", "POST"])
@login_required
def practice(prompt_id):
    prompt = WritingPrompt.query.filter_by(id=prompt_id, is_published=True).first_or_404()
    previous = WritingSubmission.query.filter_by(user_id=current_user.id, prompt_id=prompt.id).order_by(WritingSubmission.revision_number.desc()).all()
    if request.method == "POST":
        content = (request.form.get("content_text") or "").strip()
        if len(content) < 10:
            flash("Write a little more before saving this draft.", "warning")
            return redirect(url_for("writing.practice", prompt_id=prompt.id))
        if len(content) > 20000:
            flash("This draft is too long for the practice editor.", "danger")
            return redirect(url_for("writing.practice", prompt_id=prompt.id))
        metrics = _metrics(prompt, content)
        revision = (previous[0].revision_number + 1) if previous else 1
        row = WritingSubmission(user_id=current_user.id, prompt_id=prompt.id, revision_number=revision, content_text=content, **metrics)
        db.session.add(row)
        db.session.commit()
        return redirect(url_for("writing.result", submission_id=row.id))
    initial = previous[0].content_text if previous else ""
    return render_template("writing_practice.html", prompt=prompt, previous=previous, initial=initial)


@writing_bp.get("/submission/<int:submission_id>")
@login_required
def result(submission_id):
    submission = WritingSubmission.query.get_or_404(submission_id)
    if submission.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for("writing.index"))
    prior = WritingSubmission.query.filter(
        WritingSubmission.user_id == submission.user_id,
        WritingSubmission.prompt_id == submission.prompt_id,
        WritingSubmission.revision_number < submission.revision_number,
    ).order_by(WritingSubmission.revision_number.desc()).first()
    return render_template("writing_result.html", submission=submission, prior=prior)
