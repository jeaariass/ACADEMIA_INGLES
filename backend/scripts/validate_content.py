#!/usr/bin/env python3
"""
Static QA for English Practice Hub content JSON.

Run from /app inside the backend container:
    python scripts/validate_content.py

Optional:
    python scripts/validate_content.py --strict
    python scripts/validate_content.py --json-out /tmp/content_qa.json
    python scripts/validate_content.py --markdown-out /tmp/content_qa.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
RULES_PATH = ROOT / "qa" / "qa_rules.json"


@dataclass
class Issue:
    severity: str
    code: str
    file: str
    location: str
    message: str


class QA:
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.issues: list[Issue] = []
        self.stats: dict[str, Any] = {
            "files_checked": 0,
            "levels": {},
            "assessments": {},
            "questions_checked": 0,
            "passages_checked": 0,
            "topics_checked": 0,
        }
        self.question_codes: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.topic_codes: dict[str, list[str]] = defaultdict(list)
        self.assessment_codes: dict[str, list[str]] = defaultdict(list)
        self.question_prompts: list[tuple[str, str, str]] = []
        self.topic_code_set: set[str] = set()

    def add(self, severity: str, code: str, file: Path, location: str, message: str):
        self.issues.append(Issue(severity, code, str(file.relative_to(ROOT)), location, message))

    def error(self, code: str, file: Path, location: str, message: str):
        self.add("ERROR", code, file, location, message)

    def warn(self, code: str, file: Path, location: str, message: str):
        self.add("WARNING", code, file, location, message)

    def info(self, code: str, file: Path, location: str, message: str):
        self.add("INFO", code, file, location, message)


def load_json(path: Path, qa: QA) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        qa.stats["files_checked"] += 1
        return data
    except json.JSONDecodeError as exc:
        qa.error("JSON_INVALID", path, f"line {exc.lineno}", f"Invalid JSON: {exc.msg}")
    except OSError as exc:
        qa.error("FILE_READ_ERROR", path, "-", str(exc))
    return None


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s']", "", value)
    return value


def flatten_questions(data: dict[str, Any]) -> Iterable[tuple[dict[str, Any], str]]:
    for q in data.get("questions", []) or []:
        yield q, "direct"
    for p in data.get("passages", []) or []:
        for q in p.get("questions", []) or []:
            yield q, f"passage:{p.get('code', '?')}"


def all_topic_questions(topic: dict[str, Any]) -> list[dict[str, Any]]:
    out = list(topic.get("questions", []) or [])
    for passage in topic.get("passages", []) or []:
        out.extend(passage.get("questions", []) or [])
    return out


def validate_options(q: dict[str, Any], qa: QA, path: Path, location: str, rules: dict):
    valid_correct = set(rules["question_quality"]["valid_correct_options"])
    opts = []
    for key in ("a", "b", "c", "d"):
        value = str(q.get(f"option_{key}", "") or "").strip()
        opts.append(value)
        if not value:
            qa.error("OPTION_EMPTY", path, location, f"option_{key} is empty.")

    normalized = [normalize_text(x) for x in opts if x]
    if len(normalized) != len(set(normalized)):
        qa.error("OPTION_DUPLICATE", path, location, "Two or more answer options are identical after normalization.")

    correct = str(q.get("correct_option", "") or "").upper().strip()
    if correct not in valid_correct:
        qa.error("CORRECT_OPTION_INVALID", path, location, f"correct_option={correct!r}; expected A/B/C/D.")

    prompt = str(q.get("prompt", "") or "").strip()
    if len(prompt) < rules["question_quality"]["minimum_prompt_length"]:
        qa.warn("PROMPT_TOO_SHORT", path, location, f"Prompt is only {len(prompt)} characters.")

    explanation = str(q.get("explanation", "") or "").strip()
    if len(explanation) < rules["question_quality"]["minimum_explanation_length"]:
        qa.warn("EXPLANATION_TOO_SHORT", path, location, f"Explanation is only {len(explanation)} characters.")

    if prompt:
        qa.question_prompts.append((normalize_text(prompt), str(path.relative_to(ROOT)), location))

    code = str(q.get("code", "") or "").strip()
    if not code:
        qa.error("QUESTION_CODE_MISSING", path, location, "Question code is missing.")
    else:
        qa.question_codes[code].append((str(path.relative_to(ROOT)), location))

    skill = str(q.get("skill", "") or "").strip()
    allowed = set(rules["question_quality"]["valid_skills"])
    if skill and skill not in allowed:
        qa.warn("SKILL_UNKNOWN", path, location, f"Unknown skill {skill!r}.")

    qa.stats["questions_checked"] += 1


def validate_passage(p: dict[str, Any], qa: QA, path: Path, location: str, rules: dict):
    ptype = str(p.get("passage_type", "") or "")
    if ptype not in rules["question_quality"]["valid_passage_types"]:
        qa.error("PASSAGE_TYPE_INVALID", path, location, f"passage_type={ptype!r}")

    if ptype == "reading" and not str(p.get("content_text", "") or "").strip():
        qa.error("READING_TEXT_MISSING", path, location, "Reading passage has no content_text.")

    if ptype == "listening":
        if not str(p.get("audio_text", "") or "").strip():
            qa.error("LISTENING_AUDIO_TEXT_MISSING", path, location, "Listening passage has no audio_text.")
        rate = p.get("audio_rate")
        if rate is not None:
            try:
                rate_f = float(rate)
                if not 0.65 <= rate_f <= 1.30:
                    qa.warn("AUDIO_RATE_OUTLIER", path, location, f"audio_rate={rate_f}; expected roughly 0.65–1.30.")
            except (TypeError, ValueError):
                qa.error("AUDIO_RATE_INVALID", path, location, f"audio_rate={rate!r}")

    qlist = p.get("questions", []) or []
    if not qlist:
        qa.error("PASSAGE_WITHOUT_QUESTIONS", path, location, "Passage contains no questions.")

    qa.stats["passages_checked"] += 1


def validate_curriculum_file(path: Path, data: dict[str, Any], qa: QA, rules: dict):
    level = data.get("level", {}) or {}
    code = str(level.get("code", "") or "").strip()
    topics = data.get("topics", []) or []

    if not code:
        qa.error("LEVEL_CODE_MISSING", path, "level", "Missing level.code.")
        return

    qa.stats["levels"][code] = {"topics": len(topics), "questions": 0, "passages": 0}

    expected_topics = rules["curriculum"]["expected_topics_per_level"]
    if len(topics) != expected_topics:
        qa.error(
            "TOPIC_COUNT_MISMATCH", path, f"level:{code}",
            f"Found {len(topics)} topics; expected {expected_topics}."
        )

    seen_orders = []
    for idx, topic in enumerate(topics, start=1):
        tloc = f"{code}.topic[{idx}]"
        tcode = str(topic.get("code", "") or "").strip()
        if not tcode:
            qa.error("TOPIC_CODE_MISSING", path, tloc, "Topic code is missing.")
        else:
            qa.topic_codes[tcode].append(str(path.relative_to(ROOT)))
            qa.topic_code_set.add(tcode)

        order = topic.get("order")
        seen_orders.append(order)

        if not str(topic.get("title", "") or "").strip():
            qa.error("TOPIC_TITLE_MISSING", path, tloc, "Topic title is empty.")

        direct = topic.get("questions", []) or []
        passages = topic.get("passages", []) or []
        reading_count = sum(1 for p in passages if p.get("passage_type") == "reading")
        listening_count = sum(1 for p in passages if p.get("passage_type") == "listening")
        passage_q_count = sum(len(p.get("questions", []) or []) for p in passages)
        total = len(direct) + passage_q_count

        exp_direct = rules["curriculum"]["expected_direct_questions_per_topic"]
        exp_passages = rules["curriculum"]["expected_passages_per_topic"]
        exp_pq = rules["curriculum"]["expected_passage_questions_per_topic"]
        exp_total = rules["curriculum"]["expected_total_questions_per_topic"]

        if len(direct) != exp_direct:
            qa.error("DIRECT_QUESTION_COUNT_MISMATCH", path, tloc, f"Found {len(direct)} direct questions; expected {exp_direct}.")
        if len(passages) != exp_passages:
            qa.error("PASSAGE_COUNT_MISMATCH", path, tloc, f"Found {len(passages)} passages; expected {exp_passages}.")
        if passage_q_count != exp_pq:
            qa.error("PASSAGE_QUESTION_COUNT_MISMATCH", path, tloc, f"Found {passage_q_count} passage questions; expected {exp_pq}.")
        if total != exp_total:
            qa.error("TOPIC_TOTAL_QUESTION_MISMATCH", path, tloc, f"Found {total} total questions; expected {exp_total}.")
        if reading_count != rules["curriculum"]["expected_reading_passages_per_topic"]:
            qa.error("READING_PASSAGE_COUNT_MISMATCH", path, tloc, f"Found {reading_count} reading passages.")
        if listening_count != rules["curriculum"]["expected_listening_passages_per_topic"]:
            qa.error("LISTENING_PASSAGE_COUNT_MISMATCH", path, tloc, f"Found {listening_count} listening passages.")

        for qi, question in enumerate(direct, start=1):
            validate_options(question, qa, path, f"{tloc}.question[{qi}]", rules)

        for pi, p in enumerate(passages, start=1):
            ploc = f"{tloc}.passage[{pi}]"
            validate_passage(p, qa, path, ploc, rules)
            for qi, question in enumerate(p.get("questions", []) or [], start=1):
                validate_options(question, qa, path, f"{ploc}.question[{qi}]", rules)

        qa.stats["topics_checked"] += 1
        qa.stats["levels"][code]["questions"] += total
        qa.stats["levels"][code]["passages"] += len(passages)

    expected_orders = list(range(1, len(topics) + 1))
    if sorted(x for x in seen_orders if isinstance(x, int)) != expected_orders:
        qa.warn("TOPIC_ORDER_GAP", path, f"level:{code}", f"Topic orders are {seen_orders}; expected 1..{len(topics)}.")


def validate_assessment_file(path: Path, data: dict[str, Any], qa: QA, rules: dict):
    meta = data.get("assessment", {}) or {}
    acode = str(meta.get("code", "") or "").strip()
    atype = str(meta.get("assessment_type", "") or "").strip()
    questions = data.get("questions", []) or []
    passages = data.get("passages", []) or []
    total = len(questions) + sum(len(p.get("questions", []) or []) for p in passages)

    if not acode:
        qa.error("ASSESSMENT_CODE_MISSING", path, "assessment", "Assessment code is missing.")
        return

    qa.assessment_codes[acode].append(str(path.relative_to(ROOT)))
    qa.stats["assessments"][acode] = {
        "type": atype,
        "questions": total,
        "passages": len(passages),
    }

    for qi, question in enumerate(questions, start=1):
        loc = f"{acode}.question[{qi}]"
        validate_options(question, qa, path, loc, rules)
        tcode = str(question.get("topic_code", "") or "").strip()
        if tcode and tcode not in qa.topic_code_set:
            qa.error("ASSESSMENT_TOPIC_UNKNOWN", path, loc, f"topic_code={tcode!r} not found in curriculum.")

    for pi, p in enumerate(passages, start=1):
        ploc = f"{acode}.passage[{pi}]"
        validate_passage(p, qa, path, ploc, rules)
        tcode = str(p.get("topic_code", "") or "").strip()
        if tcode and tcode not in qa.topic_code_set:
            qa.error("ASSESSMENT_PASSAGE_TOPIC_UNKNOWN", path, ploc, f"topic_code={tcode!r} not found in curriculum.")
        for qi, question in enumerate(p.get("questions", []) or [], start=1):
            loc = f"{ploc}.question[{qi}]"
            validate_options(question, qa, path, loc, rules)
            q_tcode = str(question.get("topic_code", "") or "").strip()
            if q_tcode and q_tcode not in qa.topic_code_set:
                qa.error("ASSESSMENT_TOPIC_UNKNOWN", path, loc, f"topic_code={q_tcode!r} not found in curriculum.")

    # Type-specific checks
    if atype == "level":
        expected_q = rules["level_assessments"]["expected_question_count"]
        expected_p = rules["level_assessments"]["expected_passage_count"]
        if total != expected_q:
            qa.error("LEVEL_ASSESSMENT_COUNT_MISMATCH", path, acode, f"Found {total} questions; expected {expected_q}.")
        if len(passages) != expected_p:
            qa.error("LEVEL_ASSESSMENT_PASSAGE_MISMATCH", path, acode, f"Found {len(passages)} passages; expected {expected_p}.")

        sections = Counter()
        for question, _ in flatten_questions(data):
            sections[str(question.get("section", "") or "")] += 1
        expected_sections = rules["level_assessments"]["expected_sections"]
        for section, expected in expected_sections.items():
            found = sections.get(section, 0)
            if found != expected:
                qa.error("ASSESSMENT_SECTION_MISMATCH", path, acode, f"Section {section!r}: found {found}, expected {expected}.")

    if acode == rules["diagnostic"]["assessment_code"]:
        if total != rules["diagnostic"]["expected_question_count"]:
            qa.error("DIAGNOSTIC_COUNT_MISMATCH", path, acode, f"Found {total} questions.")
        if len(passages) != rules["diagnostic"]["expected_passage_count"]:
            qa.error("DIAGNOSTIC_PASSAGE_MISMATCH", path, acode, f"Found {len(passages)} passages.")

    if acode == rules["final"]["assessment_code"]:
        if total != rules["final"]["expected_question_count"]:
            qa.error("FINAL_COUNT_MISMATCH", path, acode, f"Found {total} questions.")
        if len(passages) != rules["final"]["expected_passage_count"]:
            qa.error("FINAL_PASSAGE_MISMATCH", path, acode, f"Found {len(passages)} passages.")


def duplicate_checks(qa: QA, rules: dict):
    dummy = ROOT / "content"

    for code, refs in qa.question_codes.items():
        if len(refs) > 1:
            qa.error("QUESTION_CODE_DUPLICATE", dummy, code, f"Question code occurs {len(refs)} times: {refs}")

    for code, refs in qa.topic_codes.items():
        if len(refs) > 1:
            qa.error("TOPIC_CODE_DUPLICATE", dummy, code, f"Topic code occurs in multiple files: {refs}")

    for code, refs in qa.assessment_codes.items():
        if len(refs) > 1:
            qa.error("ASSESSMENT_CODE_DUPLICATE", dummy, code, f"Assessment code occurs in multiple files: {refs}")

    exact = defaultdict(list)
    for normalized, file, loc in qa.question_prompts:
        if normalized:
            exact[normalized].append((file, loc))
    for prompt, refs in exact.items():
        if len(refs) > 1:
            qa.warn("PROMPT_EXACT_DUPLICATE", dummy, prompt[:60], f"Same normalized prompt occurs {len(refs)} times: {refs[:8]}")

    threshold = float(rules["question_quality"]["duplicate_similarity_threshold"])
    # Compare only unique normalized prompts, and only among similarly sized strings.
    unique = [(p, refs[0]) for p, refs in exact.items() if len(refs) == 1 and len(p) >= 18]
    unique.sort(key=lambda x: len(x[0]))
    for i, (a, aref) in enumerate(unique):
        for b, bref in unique[i + 1:]:
            if len(b) > len(a) * 1.25 + 10:
                break
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= threshold:
                qa.warn(
                    "PROMPT_NEAR_DUPLICATE",
                    dummy,
                    aref[1],
                    f"Similarity {ratio:.3f}: {aref} <-> {bref}"
                )


def render_markdown(qa: QA) -> str:
    errors = [i for i in qa.issues if i.severity == "ERROR"]
    warnings = [i for i in qa.issues if i.severity == "WARNING"]
    infos = [i for i in qa.issues if i.severity == "INFO"]
    lines = [
        "# English Practice Hub - Content QA Report",
        "",
        f"- Files checked: **{qa.stats['files_checked']}**",
        f"- Topics checked: **{qa.stats['topics_checked']}**",
        f"- Questions checked: **{qa.stats['questions_checked']}**",
        f"- Passages checked: **{qa.stats['passages_checked']}**",
        f"- Errors: **{len(errors)}**",
        f"- Warnings: **{len(warnings)}**",
        f"- Info: **{len(infos)}**",
        "",
        "## Level counts",
        "",
        "| Level | Topics | Questions | Passages |",
        "|---|---:|---:|---:|",
    ]
    for code, s in sorted(qa.stats["levels"].items()):
        lines.append(f"| {code} | {s['topics']} | {s['questions']} | {s['passages']} |")

    lines += ["", "## Assessments", "", "| Code | Type | Questions | Passages |", "|---|---|---:|---:|"]
    for code, s in sorted(qa.stats["assessments"].items()):
        lines.append(f"| {code} | {s['type']} | {s['questions']} | {s['passages']} |")

    lines += ["", "## Issues", ""]
    if not qa.issues:
        lines.append("No issues detected.")
    else:
        for issue in sorted(qa.issues, key=lambda x: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[x.severity], x.code, x.file)):
            lines.append(f"- **{issue.severity} · {issue.code}** — `{issue.file}` · `{issue.location}` — {issue.message}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Return non-zero when warnings exist.")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args()

    with RULES_PATH.open("r", encoding="utf-8") as fh:
        rules = json.load(fh)

    qa = QA(strict=args.strict)

    curriculum_dir = CONTENT / "curriculum"
    assessment_dir = CONTENT / "assessments"

    # Ignore support/manifest JSON files. Only academic payloads should be validated.
    def academic_json_files(folder):
        return sorted(
            path for path in folder.glob("*.json")
            if not path.name.startswith("_")
            and "manifest" not in path.name.lower()
        )

    curriculum_files = academic_json_files(curriculum_dir)
    assessment_files = academic_json_files(assessment_dir)

    if not curriculum_files:
        print(f"[qa] ERROR: no curriculum JSON files found at {curriculum_dir}", file=sys.stderr)
        return 2

    # Curriculum first so assessment topic references can be checked.
    for path in curriculum_files:
        data = load_json(path, qa)
        if isinstance(data, dict):
            validate_curriculum_file(path, data, qa, rules)

    expected_levels = set(rules["curriculum"]["expected_levels"])
    found_levels = set(qa.stats["levels"])
    missing = expected_levels - found_levels
    extra = found_levels - expected_levels
    if missing:
        qa.error("LEVEL_FILES_MISSING", CONTENT, "curriculum", f"Missing levels: {sorted(missing)}")
    if extra:
        qa.warn("LEVEL_FILES_EXTRA", CONTENT, "curriculum", f"Unexpected levels: {sorted(extra)}")

    for path in assessment_files:
        data = load_json(path, qa)
        if isinstance(data, dict):
            validate_assessment_file(path, data, qa, rules)

    duplicate_checks(qa, rules)

    errors = sum(1 for x in qa.issues if x.severity == "ERROR")
    warnings = sum(1 for x in qa.issues if x.severity == "WARNING")

    print("[qa] English Practice Hub static content validation")
    print(f"[qa] Files: {qa.stats['files_checked']}")
    print(f"[qa] Topics: {qa.stats['topics_checked']}")
    print(f"[qa] Questions: {qa.stats['questions_checked']}")
    print(f"[qa] Passages: {qa.stats['passages_checked']}")
    print(f"[qa] Errors: {errors}")
    print(f"[qa] Warnings: {warnings}")

    if errors:
        print("[qa] Structural errors:")
        for item in qa.issues:
            if item.severity == "ERROR":
                print(
                    f"[qa] ERROR {item.code}: "
                    f"{item.file} · {item.location} · {item.message}"
                )

    if warnings:
        print(
            "[qa] NOTE: warnings are editorial review signals. "
            "Use --markdown-out or --json-out for the full warning list."
        )

    for code, stat in sorted(qa.stats["levels"].items()):
        print(f"[qa] {code}: {stat['topics']} topics, {stat['questions']} questions, {stat['passages']} passages")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stats": qa.stats,
            "summary": {"errors": errors, "warnings": warnings},
            "issues": [asdict(i) for i in qa.issues],
        }
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[qa] JSON report: {args.json_out}")

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(qa), encoding="utf-8")
        print(f"[qa] Markdown report: {args.markdown_out}")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
